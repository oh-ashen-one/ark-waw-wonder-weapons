#!/usr/bin/env python3
"""Install / uninstall a locally cooked ASE mod into the CrossOver ARK client (offline, single-player).

  python3 -I tools/ark_mod_install.py install <cooked_mod_dir> --id 900000001 --name ArkMashup --map ArkMashup
  python3 -I tools/ark_mod_install.py uninstall --id 900000001
  python3 -I tools/ark_mod_install.py status

- Copies <cooked_mod_dir> to ShooterGame/Content/Mods/<id>/ and writes <id>.mod, mod.info, modmeta.info
  (layout per arkmanager: https://github.com/arkmanager/ark-server-tools tools/arkmanager).
- Backs up GameUserSettings.ini once (timestamped) and adds the id to ActiveMods= under [ServerSettings].
- Uninstall removes exactly what install created and the id from ActiveMods.
Never touches anything else. The game must be closed.
"""
import argparse, datetime, os, re, shutil, struct, subprocess, sys

ARK = os.path.expanduser("~/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/Steam/steamapps/common/ARK")
MODS = os.path.join(ARK, "ShooterGame/Content/Mods")
GUS = os.path.join(ARK, "ShooterGame/Saved/Config/WindowsNoEditor/GameUserSettings.ini")


def lp(s: str) -> bytes:
    b = s.encode("utf-8") + b"\0"
    return struct.pack("<i", len(b)) + b


def modmeta(meta: dict) -> bytes:
    out = struct.pack("<i", len(meta))
    for k, v in meta.items():
        out += lp(k) + lp(v)
    return out


def mod_info(name: str, maps: list) -> bytes:
    return lp(name) + struct.pack("<i", len(maps)) + b"".join(lp(m) for m in maps)


def dot_mod(mod_id: int, name: str, maps: list, meta: bytes) -> bytes:
    out = struct.pack("<II", mod_id, 0) + lp(name) + lp(f"../../../ShooterGame/Content/Mods/{mod_id}")
    out += struct.pack("<i", len(maps)) + b"".join(lp(m) for m in maps)
    out += bytes([0x33, 0xFF, 0x22, 0xFF, 0x02, 0x00, 0x00, 0x00, 0x01])
    return out + meta


def game_running() -> bool:
    return subprocess.run(["pgrep", "-f", r"C:\\.*[S]hooterGame\.exe"], capture_output=True).returncode == 0


def set_active(mod_id: int, add: bool):
    txt = open(GUS, encoding="utf-8-sig", errors="replace").read()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(GUS, f"{GUS}.bak-{stamp}")
    m = re.search(r"^ActiveMods=(.*)$", txt, re.M)
    ids = [i for i in (m.group(1).split(",") if m else []) if i.strip()]
    ids = [i for i in ids if i != str(mod_id)]
    if add:
        ids.insert(0, str(mod_id))
    line = "ActiveMods=" + ",".join(ids)
    if m:
        txt = txt[:m.start()] + line + txt[m.end():]
    else:
        txt = re.sub(r"^\[ServerSettings\]\s*$", "[ServerSettings]\n" + line, txt, count=1, flags=re.M)
    open(GUS, "w", encoding="utf-8").write(txt)
    print("ActiveMods ->", ",".join(ids) or "(empty)", f"(backup {GUS}.bak-{stamp})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["install", "uninstall", "status"])
    ap.add_argument("src", nargs="?")
    ap.add_argument("--id", type=int, default=900000001)
    ap.add_argument("--name", default="ArkMashup")
    ap.add_argument("--map", action="append", default=None)
    a = ap.parse_args()
    if a.cmd != "status" and game_running():
        sys.exit("ARK is running; close it first")
    dst = os.path.join(MODS, str(a.id))
    if a.cmd == "status":
        print("Mods dir:", sorted(os.listdir(MODS)))
        print([l for l in open(GUS, errors="replace") if l.startswith("ActiveMods")])
        return
    if a.cmd == "uninstall":
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        if os.path.exists(dst + ".mod"):
            os.remove(dst + ".mod")
        set_active(a.id, add=False)
        print("uninstalled", a.id)
        return
    maps = a.map or [a.name]
    if not a.src or not os.path.isdir(a.src):
        sys.exit("cooked mod dir required")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(a.src, dst)
    meta = modmeta({"ModType": "1"})
    open(os.path.join(dst, "mod.info"), "wb").write(mod_info(a.name, maps))
    open(os.path.join(dst, "modmeta.info"), "wb").write(meta)
    open(dst + ".mod", "wb").write(dot_mod(a.id, a.name, maps, meta))
    set_active(a.id, add=True)
    print("installed", a.id, "->", dst)


if __name__ == "__main__":
    main()
