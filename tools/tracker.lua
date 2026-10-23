-- SoulSilver / HeartGold tracker: memory dumper for DeSmuME
-- Load via  Tools > Lua Scripting > New Lua Script Window > Browse > Run
--
-- Writes the raw (still encrypted) bytes of your party and the enemy party to
-- ss_dump.txt. tracker.py decrypts and displays them.
-- Keep this script dumb on purpose: all the logic lives in Python.
--
-- Built to stay cheap under fast forward:
--   * uses a frame callback instead of a frameadvance loop (no coroutine switch every frame)
--   * on most frames the callback only bumps a counter
--   * memory is read in bulk, and the file is only written when the data changed
--   * one plain file write, no temp-file/rename dance

---------------------------------------------------------------- settings
local OUTPUT_FILE    = "ss_dump.txt"  -- relative to this script's folder; use a full path if needed
local UPDATE_SECONDS = 0.5            -- how often to check memory, in real seconds
local CLOCK_EVERY    = 10             -- only look at the clock every N frames
local DEBUG          = true           -- print how often the file is written (every 10 s)

-- Addresses for the US (and JP) HeartGold/SoulSilver ROM, from yPokeStats.
-- European ROMs use 0x021D110C instead.
local BASE_POINTER   = 0x021D10EC
local PARTY_OFFSET   = 0x12
local ENEMY_OFFSET   = 0x4EFD2
local SLOT_SIZE      = 0xEC           -- 236 bytes per party Pokémon
----------------------------------------------------------------

local unpack = unpack or table.unpack
local HEX_FMT = string.rep("%02x", SLOT_SIZE)

local read_range = memory.readbyterange
if not read_range then
    read_range = function(addr, len)
        local t = {}
        for i = 0, len - 1 do t[i + 1] = memory.readbyte(addr + i) end
        return t
    end
end

local function read_hex(addr)
    return string.format(HEX_FMT, unpack(read_range(addr, SLOT_SIZE)))
end

local function game_code()
    local t = read_range(0x027FFE0C, 4)
    return string.char(t[1], t[2], t[3], t[4])
end

local GAME = game_code()
local last_payload = nil
local stats = { checks = 0, writes = 0, party = 0, enemy = 0 }
local last_party, last_enemy = nil, nil

local function dump()
    stats.checks = stats.checks + 1
    local base  = memory.readdword(BASE_POINTER)   -- can change after loading a save
    local party = base + PARTY_OFFSET
    local enemy = base + ENEMY_OFFSET

    local p, e = {}, {}
    for slot = 1, 6 do
        p[slot] = "P" .. slot .. "=" .. read_hex(party + SLOT_SIZE * (slot - 1))
        e[slot] = "E" .. slot .. "=" .. read_hex(enemy + SLOT_SIZE * (slot - 1))
    end
    local ptext, etext = table.concat(p, "\n"), table.concat(e, "\n")
    local payload = string.format("base=0x%08X\n", base) .. ptext .. "\n" .. etext

    if payload == last_payload then return end
    last_payload = payload
    if DEBUG then
        if ptext ~= last_party then stats.party = stats.party + 1 end
        if etext ~= last_enemy then stats.enemy = stats.enemy + 1 end
        last_party, last_enemy = ptext, etext
    end

    local f = io.open(OUTPUT_FILE, "w")
    if not f then
        print("tracker.lua: cannot write " .. OUTPUT_FILE)
        return
    end
    f:write("frame=", emu.framecount(), "\ngame=", GAME, "\n", payload, "\n")
    f:close()
    stats.writes = stats.writes + 1
end

print("SoulSilver tracker running. Game code: " .. GAME .. " (US SoulSilver = IPGE, HeartGold = IPKE)")
print("Checking memory every " .. UPDATE_SECONDS .. "s, writing " .. OUTPUT_FILE .. " when it changes.")

-- os.clock() is real time on Windows, CPU time on some builds; os.time() is a 1-second backup.
local frames, next_check, last_second, next_report = 0, 0, os.time(), os.time() + 10

emu.registerafter(function()
    frames = frames + 1
    if frames < CLOCK_EVERY then return end
    frames = 0

    local now, second = os.clock(), os.time()
    if now >= next_check or second ~= last_second then
        next_check, last_second = now + UPDATE_SECONDS, second
        dump()
    end

    if DEBUG and second >= next_report then
        print(string.format("last 10s: %d checks, %d file writes (party changed %d, enemy changed %d)",
            stats.checks, stats.writes, stats.party, stats.enemy))
        stats = { checks = 0, writes = 0, party = 0, enemy = 0 }
        next_report = second + 10
    end
end)
