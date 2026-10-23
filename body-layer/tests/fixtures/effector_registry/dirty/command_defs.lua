-- synthetic fixture (BL-B90 Stage 0b) -- not ED source. Shape confirmed live
-- against the installed Mi-24P module, build 2.9.30.28738, 2026-10-23.
-- See aircraft-layer/research/2026-10-23-mi24p-clickabledata-forms.md Q2.
start_command	= 3000
local count = 0
local function counter()
	count = count + 1
	return count
end

-- a big Keys = { PlaneGear = 68, ... } global-iCommand table would sit
-- here in the real file, with explicit numeric values and no reset --
-- deliberately omitted: nothing in clickabledata.lua ever references it.

count = start_command
elec_commands =
{
	ACGroundPower							= counter();
	ACGeneratorLeft							= counter(),
}

count = start_command
asp_commands =
{
	Power									= counter();
	Manual_Auto								= counter();
	Range_Value								= counter();
}

count = start_command
spu8_commands = --radio stuff
{
	CMD_SPU8_TRIGGER_P						= counter();
	CMD_SPU8_O_ICS_RADIO					= counter();
}

count = start_command
device_commands = {}
for cmd_num = 1,5 do
	device_commands["Button_"..cmd_num] = counter()
end
