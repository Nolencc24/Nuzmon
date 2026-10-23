"""
Read SoulSilver/HeartGold data straight out of DeSmuME's process memory.

No Lua script runs inside the emulator, so fast forward is unaffected.

How it works
------------
DeSmuME keeps the DS's 4 MB of main RAM in one block of its own memory. The game
copies its cartridge header into DS RAM at 0x027FFE00 (= offset 0x3FFE00 into that
block), so we search DeSmuME's memory for the header text "POKEMON SS" + "IPG?"
(or "POKEMON HG" + "IPK?"). Once found:

    location in DeSmuME = start of block + (DS address - 0x02000000)

The ROM file is also loaded in memory and contains the same header, so each match
is checked by reading the game's party pointer and making sure it points inside DS RAM.

Windows uses ReadProcessMemory. Linux reads /proc/<pid>/mem (usually needs sudo).
"""

from __future__ import annotations

import struct
import sys

from .decoder import PARTY_SIZE, parse

DS_RAM_START = 0x02000000
DS_RAM_SIZE = 0x400000          # 4 MB, mirrored up to 0x02FFFFFF
HEADER_OFFSET = 0x3FFE00        # where the cartridge header copy sits in DS RAM
SIGNATURES = (b"POKEMON SS", b"POKEMON HG")
GAME_CODES = ("IPG", "IPK")     # SoulSilver, HeartGold (4th letter = region)
# DeSmuME may size its RAM block as 4, 8 or 16 MB (DS / debug / DSi modes); the header
# copy sits 0x200 bytes from the end of the block, so try each size.
RAM_BLOCK_SIZES = (0x400000, 0x800000, 0x1000000)

# Same addresses as tracker.lua (US/JP ROM; European ROMs use 0x021D110C)
BASE_POINTERS = {"E": 0x021D10EC, "J": 0x021D10EC}
BASE_POINTER_EU = 0x021D110C
PARTY_OFFSET = 0x12
ENEMY_OFFSET = 0x4EFD2

CHUNK = 16 * 1024 * 1024


class NotFound(Exception):
    """DeSmuME isn't running, or no game RAM was found in it (yet)."""


# ---------------------------------------------------------------- OS backends

class _WindowsProcess:
    def __init__(self, pid: int):
        import ctypes
        from ctypes import wintypes as wt

        self.ctypes = ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        k32.OpenProcess.restype = wt.HANDLE
        k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                          ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        k32.ReadProcessMemory.restype = wt.BOOL
        k32.CloseHandle.argtypes = [wt.HANDLE]

        fields = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                  ("AllocationProtect", wt.DWORD)]
        
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            fields.append(("PartitionId", wt.WORD))  # 64-bit layout; padding follows automatically

        fields += [("RegionSize", ctypes.c_size_t), ("State", wt.DWORD),
                   ("Protect", wt.DWORD), ("Type", wt.DWORD)]
        
        self.MBI = type("MEMORY_BASIC_INFORMATION", (ctypes.Structure,), {"_fields_": fields})
        k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(self.MBI), ctypes.c_size_t]
        k32.VirtualQueryEx.restype = ctypes.c_size_t
        self.k32 = k32

        PROCESS_QUERY_INFORMATION, PROCESS_VM_READ = 0x0400, 0x0010
        self.handle = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not self.handle:
            raise NotFound(f"Could not open DeSmuME (error {ctypes.get_last_error()}). "
                           "If DeSmuME runs as administrator, run the tracker as administrator too.")

    def regions(self):
        ctypes = self.ctypes
        mbi = self.MBI()
        addr, limit = 0, (1 << 47) if ctypes.sizeof(ctypes.c_void_p) == 8 else (1 << 31)
        MEM_COMMIT, PAGE_NOACCESS, PAGE_GUARD = 0x1000, 0x01, 0x100

        while addr < limit:
            if not self.k32.VirtualQueryEx(self.handle, addr, ctypes.byref(mbi), ctypes.sizeof(mbi)):
                break
            base, size = mbi.BaseAddress or 0, mbi.RegionSize
            if mbi.State == MEM_COMMIT and not (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) and mbi.Protect:
                yield base, size

            addr = base + size

    def read(self, addr: int, n: int) -> bytes:
        ctypes = self.ctypes
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t(0)
        if not self.k32.ReadProcessMemory(self.handle, addr, buf, n, ctypes.byref(got)) or got.value != n:
            raise OSError("ReadProcessMemory failed")
        
        return buf.raw

    def close(self):
        if self.handle:
            self.k32.CloseHandle(self.handle)
            self.handle = None


class _LinuxProcess:
    def __init__(self, pid: int):
        self.pid = pid
        try:
            self.mem = open(f"/proc/{pid}/mem", "rb", buffering=0)

        except PermissionError as e:
            raise NotFound("No permission to read DeSmuME's memory; try running with sudo.") from e
        
        except OSError as e:
            raise NotFound("DeSmuME isn't running.") from e

    def regions(self):
        with open(f"/proc/{self.pid}/maps") as f:
            for line in f:
                parts = line.split()

                if "r" not in parts[1]:
                    continue
                start, end = (int(x, 16) for x in parts[0].split("-"))
                yield start, end - start

    def read(self, addr: int, n: int) -> bytes:
        self.mem.seek(addr)
        data = self.mem.read(n)

        if len(data) != n:
            raise OSError("short read")
        
        return data

    def close(self):
        self.mem.close()


def _open_process(pid: int):
    return _WindowsProcess(pid) if sys.platform == "win32" else _LinuxProcess(pid)


def find_desmume_pid(name_hint: str = "desmume") -> int:
    import psutil

    for p in psutil.process_iter(["pid", "name"]):
        if name_hint in (p.info["name"] or "").lower():
            return p.info["pid"]
        
    raise NotFound("DeSmuME isn't running.")


# ---------------------------------------------------------------- reader

class DesmumeMemory:
    """Attach to DeSmuME and read DS addresses (0x02xxxxxx) from it."""

    def __init__(self, pid: int):
        self.pid = pid
        self.proc = _open_process(pid)
        self.ram_base = None     # where DS address 0x02000000 lives inside DeSmuME
        self.ram_mask = DS_RAM_SIZE - 1
        self.scanned = 0
        self.game = None
        self.base_pointer = None

    def close(self):
        self.proc.close()

    def read_ds(self, addr: int, n: int) -> bytes:
        return self.proc.read(self.ram_base + ((addr - DS_RAM_START) & self.ram_mask), n)

    def u32(self, addr: int) -> int:
        return struct.unpack("<I", self.read_ds(addr, 4))[0]

    def find_headers(self):
        """Yield (address, game code) for every 'POKEMON SS/HG' header in DeSmuME's memory."""
        overlap = 16
        for start, size in self.proc.regions():
            pos = 0

            while pos < size:
                n = min(CHUNK, size - pos)
                try:
                    chunk = self.proc.read(start + pos, n)

                except OSError:
                    break

                self.scanned += n
                for sig in SIGNATURES:
                    i = chunk.find(sig)

                    while i != -1:
                        code = chunk[i + 12:i + 16]

                        if len(code) == 4 and code[:3].decode("latin-1") in GAME_CODES:
                            yield start + pos + i, code.decode("latin-1")

                        i = chunk.find(sig, i + 1)

                if n < CHUNK:
                    break

                pos += n - overlap

    def locate(self, report=None) -> None:
        """Search DeSmuME's memory for DS main RAM. Takes a second or two.

        report: optional function called with a line of text for each header found
        (used by main.py --diagnose).
        """
        self.scanned = 0
        for addr, code in self.find_headers():
            if report:
                report(f"  header '{code}' at 0x{addr:X}")

            for block in RAM_BLOCK_SIZES:
                ok, why = self._try_candidate(addr - (block - 0x200), block - 1, code)

                if report:
                    report(f"    as end of a {block >> 20} MB RAM block: {why}")
                if ok:
                    return
                
        raise NotFound("DeSmuME is running but no SoulSilver/HeartGold RAM was found yet. "
                       "Load your save and get past the title screen.")

    def _try_candidate(self, ram_base: int, mask: int, code: str):
        self.ram_base, self.ram_mask = ram_base, mask
        try:
            ptr_addr = BASE_POINTERS.get(code[3], BASE_POINTER_EU)
            ptr = self.u32(ptr_addr)

        except OSError:
            return False, "unreadable (not RAM)"
        # The ROM's own header also matches; real RAM has an aligned pointer into DS RAM.
        # It's 0 on the title screen, so we only lock on once you're in-game.

        if ptr == 0:
            return False, f"party pointer at 0x{ptr_addr:08X} is 0 (title screen?)"
        
        # The pointer itself needn't be aligned (HGSS adds 0x12), but the party it leads to is.
        if (ptr + PARTY_OFFSET) % 4 or not DS_RAM_START < ptr < DS_RAM_START + DS_RAM_SIZE - ENEMY_OFFSET:
            return False, f"party pointer at 0x{ptr_addr:08X} = 0x{ptr:08X}, not a valid RAM address"
        
        self.game, self.base_pointer = code, ptr_addr

        return True, f"OK, party pointer = 0x{ptr:08X}"
    

    def snapshot(self) -> dict:
        """Raw encrypted bytes for 6 party + 6 enemy slots, plus all of DS RAM.

        Reading the whole 4 MB at once is a single fast copy and lets us search it for
        the in-battle copies of the active Pokémon.
        """
        ram = self.read_ds(DS_RAM_START, DS_RAM_SIZE)
        base = struct.unpack_from("<I", ram, self.base_pointer - DS_RAM_START)[0]
        if not DS_RAM_START < base < DS_RAM_START + DS_RAM_SIZE - ENEMY_OFFSET - PARTY_SIZE * 6:
            empty = [bytes(PARTY_SIZE)] * 6
            return {"base": base, "party": empty, "enemy": empty, "ram": ram}
        
        p = base + PARTY_OFFSET - DS_RAM_START
        e = base + ENEMY_OFFSET - DS_RAM_START
        split = lambda o: [ram[o + i * PARTY_SIZE:o + (i + 1) * PARTY_SIZE] for i in range(6)]

        return {"base": base, "party": split(p), "enemy": split(e), "ram": ram}


# ---------------------------------------------------------------- diagnostics

def diagnose(pid: int | None = None) -> None:
    """python main.py --diagnose : print what the tracker sees inside DeSmuME."""
    import platform

    import psutil

    from .battle import BM_HP, BattleHP

    print(f"Python {platform.python_version()} {platform.architecture()[0]} on {platform.platform()}")
    try:
        pid = pid or find_desmume_pid()

    except NotFound as e:
        print(e)
        return
    
    proc = psutil.Process(pid)
    print(f"DeSmuME process: {proc.name()} (pid {pid}), exe: {proc.exe()}")
    try:
        mem = DesmumeMemory(pid)
    except NotFound as e:
        print(e)
        return
    
    regions = list(mem.proc.regions())
    print(f"Readable memory regions: {len(regions)}, total {sum(s for _, s in regions) / 2**20:.0f} MB")
    print("Searching for the game header…")

    try:
        mem.locate(report=print)
        print(f"\nFOUND: game {mem.game}, DS RAM at 0x{mem.ram_base:X} "
              f"({(mem.ram_mask + 1) >> 20} MB block)")
        snap = mem.snapshot()
        names = [(m.species, f"Lv{m.level}", f"{m.hp}/{m.max_hp}") if m else None
                 for m in map(parse, snap["party"])]
        
        print("Party:", names)
        bh = BattleHP()
        for label, raws in (("party", snap["party"]), ("enemy", snap["enemy"])):
            for slot, mon in enumerate(map(parse, raws), 1):
                for off in (bh.find_all(snap["ram"], mon) if mon else []):
                    hp, mx = struct.unpack_from("<iI", snap["ram"], off + BM_HP)
                    print(f"  battle copy of {label} slot {slot} ({mon.species}) at "
                          f"0x{DS_RAM_START + off:08X}: HP {hp}/{mx}")
    except NotFound as e:
        print(f"\nNOT FOUND. Scanned {mem.scanned / 2**20:.0f} MB. {e}")
    mem.close()
