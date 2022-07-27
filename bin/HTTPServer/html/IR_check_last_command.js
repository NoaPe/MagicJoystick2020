function load_IR_check()
{   
    let button_TV = [
        "svg_icon/button_power.svg", "svg_icon/button_1.svg", "svg_icon/button_2.svg", "svg_icon/button_3.svg", 
        "svg_icon/mute.svg", "svg_icon/button_4.svg", "svg_icon/button_5.svg", "svg_icon/button_6.svg", 
        "svg_icon/volume_up.svg", "svg_icon/button_7.svg", "svg_icon/button_8.svg", "svg_icon/button_9.svg", 
        "svg_icon/volume_down.svg", "svg_icon/up.svg", "svg_icon/button_0.svg", "",
        "svg_icon/left.svg", "svg_icon/ok.svg", "svg_icon/right.svg", "",
        "svg_icon/TV_info.svg", "svg_icon/down.svg", "svg_icon/TV_home.svg", "svg_icon/TV_source.svg", 
        "svg_icon/TV_menu.svg", "svg_icon/TV_tools.svg", "svg_icon/TV_return.svg", "svg_icon/TV_exit.svg"
    ]
    function last_command_id()
    {   
        $.ajax({
            type: "POST",
            url: "TV_A/last-validate",
            success: function(data){
                if(data !== -1){
                    document.getElementById("last_command_id").style.backgroundImage = "url(" + button_TV[data] + ")";
                }
            },
            error: function(errMsg){
            }
        });
    }

    last_command_id();
}