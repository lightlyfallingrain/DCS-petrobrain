-- synthetic fixture (BL-B90 Stage 0b) -- deliberately malformed
-- device_commands loop, to exercise CommandDefsParseError's fail-closed
-- behaviour: the loop body's key expression does not match the single
-- known shape (`<table>["prefix"..VAR] = counter()`).
start_command	= 3000
local count = 0
local function counter()
	count = count + 1
	return count
end

count = start_command
device_commands = {}
for cmd_num = 1,5 do
	device_commands["Button_"..cmd_num.."X"] = counter()
end
