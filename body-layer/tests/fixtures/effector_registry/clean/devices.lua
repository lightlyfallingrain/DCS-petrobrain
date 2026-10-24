-- synthetic fixture (BL-B90 Stage 0b) -- not ED source. Shape confirmed live
-- against the installed Mi-24P module, build 2.9.30.28738, 2026-10-23.
-- See aircraft-layer/research/2026-10-23-mi24p-clickabledata-forms.md Q1.
local count = 0
local function counter()
	count = count + 1
	return count
end

devices = {}
devices["ELEC_INTERFACE"]			= counter()
devices["FUELSYS_INTERFACE"]		= counter()
devices["ASP_17V"]					= counter()
devices["SPU_8"]					= counter()
devices["I9K113"]					= counter()
