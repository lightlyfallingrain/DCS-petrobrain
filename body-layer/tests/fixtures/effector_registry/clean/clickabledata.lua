-- synthetic fixture (BL-B90 Stage 0b) -- not ED source. Shape confirmed live
-- against the installed Mi-24P module, build 2.9.30.28738, 2026-10-23.
-- See aircraft-layer/research/2026-10-23-mi24p-clickabledata-forms.md Q4-Q7.
elements = {}

elements["WEAP-SIGHT-ON-PFF-PTR"]	= default_2_position_tumb(_("Sight Power ON/OFF"), devices.ASP_17V, asp_commands.Power, 529, nil, 1)

elements["ASP-MANUAL-AUTO-PTR"]	= default_3_position_tumb(_("Sight Mode MANUAL/AUTO"), devices.ASP_17V, asp_commands.Manual_Auto, 553, false, nil, false, 0, {-1,1})

elements["ASP-RANGE-AXIS-PTR"]	= default_axis(_("Sight Range"), devices.ASP_17V, asp_commands.Range_Value, 552, 0.0, 1/5, true, false, false, nil, nil)

elements["HELPER-SHOW-MENU-PTR"]	= default_button(_("Show AI Menu"), devices.SPU_8, device_commands.Button_1, 999, anim_speed_default/5)

elements[" CONTROL-COVER-PRIORITY-PTR"] = default_square_button(_("Cover, priority"), devices.ELEC_INTERFACE, device_commands.Button_2, 700, nil)

elements["RADIO-ICS-SWITCH-PTR"]	= default_2_position_tumb(_("Radio/ICS Switch"), devices.SPU_8, spu8_commands.CMD_SPU8_O_ICS_RADIO, 660, nil, 1)

elements["STICK-PTT-PTR"]	= {
	class 				= {class_type.BTN, class_type.BTN},
	hint  				= _("Trigger Button, RADIO(LMB)/ICS(RMB)"),
	device 				= devices.SPU_8,
	action 				= {spu8_commands.CMD_SPU8_TRIGGER_P, spu8_commands.CMD_SPU8_TRIGGER_P},
	stop_action 		= {spu8_commands.CMD_SPU8_TRIGGER_P, spu8_commands.CMD_SPU8_TRIGGER_P},
	arg 				= {738, 738},
	arg_value			= {1.0, 0.5},
	arg_lim 			= {{0.0, 1.0}, {0.0, 0.5}},
	updatable			= true,
	use_release_message = {true},
	crew_member_access  = {0}
}

elements["STICK-BRAKE-PTR"] = default_button(_("Brake"), devices.ELEC_INTERFACE, device_commands.Button_3, 701, nil)
elements["STICK-BRAKE-PTR"].crew_member_access  = {0}

elements["DOUBLE-CMD-PTR"] = default_button_tumb(_("Double command demo"), devices.SPU_8, spu8_commands.CMD_SPU8_TRIGGER_P, spu8_commands.CMD_SPU8_O_ICS_RADIO, 702, nil, 1)
