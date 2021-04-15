#!/python3
import can2RNET
import threading
import argparse
import time
import socket
import sys
import struct
import binascii
import logging
from can2RNET import can2RNET
from can2RNET.RnetDissector import RnetDissector

logger = can2RNET.logger

JSM_INIT_FILE = 'jsm_init.log'

"""
Rnet JSM init sequence recorder and playback
Must use a raspberry + Dual Can board architecture

Will be placed between JSM and main controller to log all messages with source name
in case of record mode, or replace JSM incase of playback.

For the recording init sequence, the following frame sequences will
be tagged:

    JSM   0000006xxxx
    MOTOR 0000006xxxx
    => Init sequence done

    Then, waiting for either JoyPosition frame or MaxSpeed frame
    to get the JSM identifier value.

    Then init sequence recording is completed.

"""


"""
R-net class for single raspi and pican dual port logging
"""
class RnetDualLogger(threading.Thread):

    jsm_id = False
    init = False
    joy_subtype = None

    def __init__(self, logfile):
        self.cansocket0 = None
        self.cansocket1 = None
        self.logfile = logfile

        threading.Thread.__init__(self)
        logger.info("Opening socketcan")
        try:
            self.cansocket0 = can2RNET.opencansocket(0)
        except:
            logger.error("socketcan can0 cannot be opened! Check connectivity")
            sys.exit(1)
        try:
            self.cansocket1 = can2RNET.opencansocket(1)
        except:
            logger.error("socketcan can1 cannot be opened! Check connectivity")
            sys.exit(1)


    """
    used for single raspi and pican dual config
    """
    def start_daemons(self):

        # launch daemon
        logger.debug("Starting Rnet Dual daemons")
        daemon0 = threading.Thread(target=self.rnet_daemon, args=[self.cansocket0, self.cansocket1, 'PORT0'], daemon=True)
        daemon0.start()
        daemon1 = threading.Thread(target=self.rnet_daemon, args=[self.cansocket1, self.cansocket0, 'PORT1'], daemon=True)
        daemon1.start()
        return daemon0, daemon1


    """
    Endless loop waiting for Rnet frames
    Each frame is logged and forwarded to remote server
    """
    def rnet_daemon(self, listensock, sendsock, logger_tag):
        logger.debug("Rnet listener daemon started")
        is_motor = False

        while self.init is False or self.jsm_id is False:
            rnetFrame = can2RNET.canrecv(listensock)
            frameToLog  = binascii.hexlify(rnetFrame)
            logger.debug('%s:%s:%s\n' %(time.time(), logger_tag, frameToLog))
            self.logfile.write('%s:%s:%s\n' %(time.time(), logger_tag, frameToLog))
            can2RNET.cansendraw(sendsock, rnetFrame)

            # Check end of init condition
            __, subType, frameName, __ = RnetDissector.getFrameType(rnetFrame)
            if frameName == 'END_OF_INIT':
                self.init = True
            
            # Check current thread is MOTOR or JMS
            if frameName == 'PMTX_CONNECT':
                logger.debug('********** PMTX_CONNECT frame received **********\n')
                is_motor = True

            # In case thread is JSM side, wait for 
            # a joy position to record JSM ID
            if is_motor is False and self.init is True:
                if frameName == 'JOY_POSITION':
                    logger.debug('********** Got JMS ID: 0x%x **********\n' %subType)
                    self.logfile.write('-1.0:JOY_SUBTYPE:0x%x\n' %subType)
                    self.jsm_id = True



"""
JSMiser class will send the JSM init sequence to the motor
so the raspberry will act in place of the JSM 
"""
class JSMiser(threading.Thread):

    """
    Get the JSM init sequence file,
    Then connect the Rnet socket to the correct interface
    """
    def __init__(self):

        try:
            with open(JSM_INIT_FILE,"r") as infile:
                self.jsm_cmds = infile.readlines()
        except:
            logger.error("The JMS init file %s is not present, please run JSM init recorder 'RnetCtrlInit.py' to create it" %JSM_INIT_FILE)
            sys.exit(1)

        if 'PORT0' in self.jsm_cmds[0]:
            logger.info("JSM connected on port0 and motor on port1")
            self.motor_port = 1
            self.jsm_port = 0
        else:
            logger.info("JSM connected on port1 and motor on port0")
            self.motor_port = 0
            self.jsm_port = 1

        # Set initial timeFrame
        self.timeFrame = float(self.jsm_cmds[0].split(':')[0])

        # Retreive the JSM ID from logs:
        for line in self.jsm_cmds:
            if 'JOY_SUBTYPE' in line:
                self.jsm_subtype = int(line.split(':')[2],16)
                logger.info("JSM subtype: 0x%x" %self.jsm_subtype)



        # Open motor can socket, assuming at first that the port is identical
        # to the init file. If not, try the other port as init sequence recording
        # is done on a dual port pican, but final project can use a less expensive
        # single port pican board.
        threading.Thread.__init__(self)
        logger.info("Opening socketcan")
        try:
            self.motor_cansocket = can2RNET.opencansocket(self.motor_port)
        except:
            logger.error("socketcan %d cannot be opened! Trying the other port" %self.motor_port)
            # Try the other socket as recording can be done on a dual pican but the environment
            # raspberry controller can use a single port pincan
            try:
                self.motor_cansocket = can2RNET.opencansocket(self.jsm_port)
            except:
                logger.error("socketcan %d cannot be opened either! Check connectivity" %self.jsm_port)
                sys.exit(1)



    """
    Start JSM init sequence, blocking call until init sequence
    fully completed.
    """
    def jsm_start(self):
        daemon = threading.Thread(target=self.init_daemon, args=[], daemon=True)
        daemon.start()
        daemon.join()

        print("************************* POWER ON DONE **********************")
        return self.jsm_subtype


    def get_next_frame(self, idx):
        timeFrame, port, frame = self.jsm_cmds[idx].split(':')
        if 'PORT' in port:
            bin_frame = binascii.unhexlify(frame.strip("\n").split("'")[1])
            return float(timeFrame), port, bin_frame
        else:
            return -1.0, 'NONE', b'\x00'

    """
    Will send the frames stored in the init file and wait for Motor answer
    Once done thread exits
    """
    def init_daemon(self):
        logger.debug("Rnet JSM init daemon started")
        frame_idx = 0
        JSMport = "PORT%d" %self.jsm_port
        MOTORport = "PORT%d" %self.motor_port
        max_idx = len(self.jsm_cmds)

        logger.debug("Proceeding a total of %d frames" %max_idx)

        while frame_idx < max_idx:

            currentTimeFrame, port, frame = self.get_next_frame(frame_idx)


            if port == JSMport:
                RnetDissector.printFrame(frame)
                time.sleep(currentTimeFrame - self.timeFrame )
                logger.debug("%d: sleep(%s) - Sending JSM frame %s" %(frame_idx, currentTimeFrame - self.timeFrame ,binascii.hexlify(frame)))
                # print("%r: sleep(%s) - Sending JSM frame %s" %(frame_idx,  currentTimeFrame - self.timeFrame,binascii.hexlify(frame)))
                can2RNET.cansendraw(self.motor_cansocket, frame)

            elif port == MOTORport:
                RnetDissector.printFrame(frame)
                rnetFrame = can2RNET.canrecv(self.motor_cansocket)
                logger.debug('%d: Receive MOTOR frame %s\n' %(frame_idx, binascii.hexlify(rnetFrame)))

            else:
                logger.debug('%d: %r / %r Unsupported frame: %r, %r' %(frame_idx, JSMport, MOTORport, port, frame))
                pass

            self.timeFrame =  currentTimeFrame
            frame_idx += 1


"""
Argument parser definition
"""
def parseInputs():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", help="Enable debug messages", action="store_true")
    parser.add_argument("-t", "--test_init", help="Test init sequense", action="store_true")
    return parser.parse_args()



"""
Configuration using one raspi with dual port pican boards.
"""
def picanDualCaseInit():
    # Start Rnet listener daemon
    with open(JSM_INIT_FILE,"w") as outfile:

        # Connect and initialize Rnet controller
        # Will listen for Rnet frames and transmit
        # them to other Rnet Port
        rnet = RnetDualLogger(outfile)
        daemon0, daemon1 = rnet.start_daemons()

        daemon0.join()
        daemon1.join()



if __name__ == "__main__":

    # Parse input args
    args = parseInputs()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.test_init:
        jsm = JSMiser()
        jsm.jsm_start()


    else:
        picanDualCaseInit()
