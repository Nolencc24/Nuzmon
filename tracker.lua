-- SoulSilver / HeartGold tracker: memory dumper for DeSmuME
-- Load via  Tools > Lua Scripting > New Lua Script Window > Browse > Run
--
-- Every UPDATE_FRAMES frames this writes the raw (still encrypted) bytes of your
-- party and the enemy party to ss_dump.txt. tracker.py decrypts and displays them.
-- Keep this script dumb on purpose: all the logic lives in Python.

---------------------------------------------------------------- settings
local OUTPUT_FILE   = "ss_dump.txt"  -- relative to this script's folder; use a full path if needed
local UPDATE_FRAMES = 15             -- 60 frames = 1 second

-- Addresses for the US (and JP) HeartGold/SoulSilver ROM, from yPokeStats.
-- European ROMs use 0x021D110C instead.
local BASE_POINTER  = 0x021D10EC
local PARTY_OFFSET  = 0x12
local ENEMY_OFFSET  = 0x4EFD2
local SLOT_SIZE     = 0xEC           -- 236 bytes per party Pokémon
----------------------------------------------------------------

local function read_hex(addr, len)
    local t = {}
    for i = 0, len - 1 do
        t[#t + 1] = string.format("%02x", memory.readbyte(addr + i))
    end
    return table.concat(t)
end

local function game_code()
    local s = ""
    for i = 0, 3 do s = s .. string.char(memory.readbyte(0x027FFE0C + i)) end
    return s
end

local function dump()
    -- Re-read the pointer every time: it can change after loading a save.
    local base  = memory.readdword(BASE_POINTER)
    local party = base + PARTY_OFFSET
    local enemy = base + ENEMY_OFFSET

    local lines = {
        "frame=" .. emu.framecount(),
        "game=" .. game_code(),
        string.format("base=0x%08X", base),
    }
    for slot = 1, 6 do
        lines[#lines + 1] = "P" .. slot .. "=" .. read_hex(party + SLOT_SIZE * (slot - 1), SLOT_SIZE)
    end
    for slot = 1, 6 do
        lines[#lines + 1] = "E" .. slot .. "=" .. read_hex(enemy + SLOT_SIZE * (slot - 1), SLOT_SIZE)
    end

    -- Write to a temp file then swap it in, so Python never reads a half-written file.
    local tmp = OUTPUT_FILE .. ".tmp"
    local f = io.open(tmp, "w")
    if not f then
        print("tracker.lua: cannot write " .. tmp)
        return
    end
    f:write(table.concat(lines, "\n"), "\n")
    f:close()
    os.remove(OUTPUT_FILE)
    os.rename(tmp, OUTPUT_FILE)
end

print("SoulSilver tracker running. Game code: " .. game_code() .. " (US SoulSilver = IPGE, HeartGold = IPKE)")
print("Writing to " .. OUTPUT_FILE .. " every " .. UPDATE_FRAMES .. " frames.")

while true do
    if emu.framecount() % UPDATE_FRAMES == 0 then
        dump()
    end
    gui.text(2, 2, "tracker", "#7fffd4")
    emu.frameadvance()
end
