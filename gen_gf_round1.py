r"""GHOST FRONT -- ART ROUND 1 (the work order, through ComfyUI).

Same HTTP pattern as the longnight rounds: port 8188, SDXL base, don't
touch the user's graph. Two job types:

  img2img  -- pose synthesis from a reference frame of the EXISTING cast,
              so the new plates keep the character. Init images ship in
              Downloads\gf-art\refs; denoise per job.
  txt2img  -- two brand-new enemies, in the cast's own look.

Figures are prompted onto a plain dark field; the cutting pass on the
other side (modal background removal, content crop, figh registration)
turns them into ARTDATA strips.

Output -> C:\Users\Admin\Downloads\gf-art\<group>\<name>.png
Log    -> C:\Users\Admin\Downloads\gf-art\round1_log.txt
"""
import json, urllib.request, urllib.error, time, os, sys, base64

ROOT = r"C:\Users\Admin\Downloads\gf-art"
LOG  = os.path.join(ROOT, "round1_log.txt")
os.makedirs(ROOT, exist_ok=True)
class Tee:
    def __init__(self,p): self.f=open(p,"w",encoding="utf-8",buffering=1); self.o=sys.__stdout__
    def write(self,x):
        try: self.o.write(x)
        except Exception: pass
        self.f.write(x)
    def flush(self):
        try: self.o.flush()
        except Exception: pass
        self.f.flush()
sys.stdout=Tee(LOG); sys.stderr=sys.stdout

PORTS=[8188,8000,8189]
CKPT="sd_xl_base_1.0.safetensors"
REFS=os.path.join(ROOT,"refs")

STYLE=("dark WW2 horror game sprite, full-length character, side view facing left, "
 "detailed painted illustration, muted olive charcoal bone palette, grim 1944 "
 "battlefield, gritty painterly texture, hard rim light, single subject centred, "
 "full body visible head to boots, feet at the bottom, plain flat very dark "
 "background, no text, no watermark")
NEG=("text, letters, watermark, signature, photo, photorealistic, 3d render, "
 "blurry, lowres, cropped, multiple subjects, collage, cute, chibi, bright "
 "background, white background, frame, border")

def port():
    for p in PORTS:
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/system_stats"%p, timeout=3)
            print("port", p); return p
        except Exception: pass
    print("NO COMFYUI REACHABLE -- is it running?"); sys.exit(2)

P=port()
BASE="http://127.0.0.1:%d"%P

def api(path, payload=None):
    req=urllib.request.Request(BASE+path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=600).read())

def upload(path):
    name=os.path.basename(path)
    body=b""
    bo=b"----gfb"
    with open(path,"rb") as f: data=f.read()
    body+=b"--"+bo+b"\r\nContent-Disposition: form-data; name=\"image\"; filename=\""+name.encode()+b"\"\r\nContent-Type: image/png\r\n\r\n"+data+b"\r\n--"+bo+b"--\r\n"
    req=urllib.request.Request(BASE+"/upload/image", data=body,
        headers={"Content-Type":"multipart/form-data; boundary="+bo.decode()})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())["name"]

def wait(pid):
    while True:
        h=api("/history/"+pid) if False else json.loads(urllib.request.urlopen(BASE+"/history/"+pid, timeout=30).read())
        if pid in h and h[pid].get("outputs"): return h[pid]["outputs"]
        time.sleep(1.0)

def fetch(outs, dest):
    for node in outs.values():
        for im in node.get("images",[]):
            q="filename=%s&subfolder=%s&type=%s"%(
                urllib.parse.quote(im["filename"]), urllib.parse.quote(im.get("subfolder","")), im.get("type","output"))
            data=urllib.request.urlopen(BASE+"/view?"+q, timeout=120).read()
            open(dest,"wb").write(data); return True
    return False
import urllib.parse

def t2i(prompt, seed, w=768, h=1024, steps=28, cfg=6.5):
    g={
     "1":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":CKPT}},
     "2":{"class_type":"CLIPTextEncode","inputs":{"text":STYLE+", "+prompt,"clip":["1",1]}},
     "3":{"class_type":"CLIPTextEncode","inputs":{"text":NEG,"clip":["1",1]}},
     "4":{"class_type":"EmptyLatentImage","inputs":{"width":w,"height":h,"batch_size":1}},
     "5":{"class_type":"KSampler","inputs":{"model":["1",0],"positive":["2",0],"negative":["3",0],
          "latent_image":["4",0],"seed":seed,"steps":steps,"cfg":cfg,
          "sampler_name":"dpmpp_2m","scheduler":"karras","denoise":1.0}},
     "6":{"class_type":"VAEDecode","inputs":{"samples":["5",0],"vae":["1",2]}},
     "7":{"class_type":"SaveImage","inputs":{"images":["6",0],"filename_prefix":"gf"}}}
    return g

def i2i(ref, prompt, seed, den=0.55, steps=30, cfg=6.0):
    g={
     "1":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":CKPT}},
     "2":{"class_type":"CLIPTextEncode","inputs":{"text":STYLE+", "+prompt,"clip":["1",1]}},
     "3":{"class_type":"CLIPTextEncode","inputs":{"text":NEG,"clip":["1",1]}},
     "L":{"class_type":"LoadImage","inputs":{"image":ref}},
     "U":{"class_type":"ImageScale","inputs":{"image":["L",0],"width":768,"height":768,
          "upscale_method":"lanczos","crop":"disabled"}},
     "E":{"class_type":"VAEEncode","inputs":{"pixels":["U",0],"vae":["1",2]}},
     "5":{"class_type":"KSampler","inputs":{"model":["1",0],"positive":["2",0],"negative":["3",0],
          "latent_image":["E",0],"seed":seed,"steps":steps,"cfg":cfg,
          "sampler_name":"dpmpp_2m","scheduler":"karras","denoise":den}},
     "6":{"class_type":"VAEDecode","inputs":{"samples":["5",0],"vae":["1",2]}},
     "7":{"class_type":"SaveImage","inputs":{"images":["6",0],"filename_prefix":"gf"}}}
    return g

def run(group, name, graph):
    d=os.path.join(ROOT, group); os.makedirs(d, exist_ok=True)
    dest=os.path.join(d, name+".png")
    if os.path.exists(dest): print("  skip (exists)", name); return
    pid=api("/prompt", {"prompt":graph})["prompt_id"]
    outs=wait(pid)
    ok=fetch(outs, dest)
    print("  saved" if ok else "  FAILED", name)

UP={}
def ref(n):
    if n not in UP: UP[n]=upload(os.path.join(REFS, n+".png"))
    return UP[n]

SEED=171944
J=[]
def job(group,name,graph): J.append((group,name,graph))

# ---------- A. THE PLAYER (tier 0, bare) : locomotion he never had -------
HB="the same man as the reference: bare-headed dark-haired American soldier, white shirt, braces, rolled sleeves, orange grafted forearms, dark trousers"
for nm,pp,dn in [
  ("idle_1", "standing at rest, weight even, arms loose at sides, breathing", .52),
  ("idle_2", "standing at rest, weight shifted to back foot, chest risen mid-breath", .55),
  ("run_1",  "sprinting, right leg extended forward, left arm swung forward, full stride", .62),
  ("run_2",  "sprinting, legs passing under the body mid-stride, low crouch", .62),
  ("run_3",  "sprinting, left leg extended forward, right arm swung forward, full stride", .62),
  ("jump_1", "crouched deep about to leap, knees bent, arms back", .62),
  ("jump_2", "leaping in mid-air, knees tucked, arms out", .65),
  ("jump_3", "falling, legs extended down, arms raised for balance", .65),
  ("crouch_1","kneeling on one knee, alert, one hand on the ground", .6),
  ("reload_1","standing, both hands working at the pistol at chest height, head down", .58),
  ("reload_2","standing, slapping a magazine into a pistol, elbow high", .6),
]:
    job("HAWKEB", nm, i2i(ref("HAWKEB_walk"), HB+", "+pp, SEED+len(J), den=dn))

# ---------- B. THE ARMOURED MAN (tier 2): locomotion in his own armour ---
HA="the same man as the reference: American soldier in black tactical body armour and combat helmet"
for nm,pp,dn in [
  ("idle_1","standing at rest, rifle held low across the body, weight even", .5),
  ("idle_2","standing at rest, slight shift, scanning right", .55),
  ("walk_1","walking, right foot planted forward, deliberate patrol pace", .6),
  ("walk_2","walking, feet passing mid-step", .6),
  ("walk_3","walking, left foot planted forward", .6),
  ("run_1","running hard, right leg forward, body leaning into it", .62),
  ("run_2","running hard, legs crossing mid-stride", .62),
  ("run_3","running hard, left leg forward", .62),
]:
    job("HAWKEA", nm, i2i(ref("HAWKEA_attack"), HA+", "+pp, SEED+len(J), den=dn))

# ---------- C. BOSS DEATH PLATES -----------------------------------------
for src,g2,frames in [
 ("KNOCHEN_idle","KNOCHEN",[("death_1","the armoured giant buckling at the knees, arms dropping, head bowed",.6),
                            ("death_2","the armoured giant collapsed face-down in the mud, inert, dust settling",.68)]),
 ("CHIMAERE_idle","CHIMAERE",[("death_1","the flesh mass sagging sideways, heads limp",.6),
                              ("death_2","the flesh mass collapsed into a heap on the ground, still",.68)]),
 ("EISWITWE_idle","EISWITWE",[("death_1","the spider machine with legs buckled, dome cracked",.6),
                              ("death_2","the spider machine flat on the ground, legs splayed dead, smoke",.68)]),
 ("TRUEMMER_idle","TRUEMMER",[("death_1","the rubble machine spilling its load, frame tilting",.6),
                              ("death_2","the rubble machine collapsed into its own heap of masonry",.68)]),
 ("PENDEL_idle","PENDEL",[("death_1","the bell machine cracked open, energy venting from the sphere",.6),
                          ("death_2","the bell machine shattered on the floor, dark and dead",.68)]),
]:
    for nm,pp,dn in frames: job(g2, nm, i2i(ref(src.replace("_idle","_idle")), pp+", same machine as the reference", SEED+len(J), den=dn))

# ---------- D. SINGLE-FRAME ACTORS GET FRAMES ----------------------------
for nm,pp,dn in [
 ("fire_1","the wolf-headed machine-gun team firing, muzzle flash, belt feeding", .55),
 ("fire_2","the wolf-headed machine-gun team firing, gunner leaning into recoil", .6),
 ("reload_1","the wolf-headed machine-gun team changing the belt, loader working", .6),
]:
    job("MGTEAM", nm, i2i(ref("MGTEAM_fire"), pp+", same team as the reference", SEED+len(J), den=dn))
for nm,pp,dn in [
 ("walk_1","the huge armoured mech mid-step, right leg forward", .55),
 ("walk_2","the huge armoured mech mid-step, left leg forward", .6),
 ("attack_1","the huge armoured mech punching forward with a piston fist", .6),
]:
    job("PANZER", nm, i2i(ref("PANZER_idle"), pp+", same machine as the reference", SEED+len(J), den=dn))

# ---------- E. TWO NEW ENEMIES (go crazy, but in the cast's cloth) -------
for nm,pp in [
 ("idle_1","a snarling armoured attack hound, wolf-sized, steel plates bolted along its spine and skull, standing alert side-on"),
 ("run_1","the same armoured attack hound sprinting, full gallop, jaw open"),
 ("run_2","the same armoured attack hound mid-gallop, legs gathered"),
 ("lunge_1","the same armoured attack hound leaping fangs-first"),
 ("death_1","the same armoured attack hound collapsed on its side, plates scorched"),
]:
    job("PANZERHUND", nm, t2i(pp+", WW2 German experiment, riveted steel, red harness detail", SEED+len(J)))
for nm,pp in [
 ("idle_1","a gaunt wolf-headed sniper in a hooded camouflage shroud, long scoped rifle, standing hunched side-on"),
 ("aim_1","the same hooded wolf sniper kneeling, rifle raised to the shoulder, aiming"),
 ("fire_1","the same hooded wolf sniper firing, muzzle flash at the barrel"),
 ("death_1","the same hooded wolf sniper crumpled, rifle fallen beside"),
]:
    job("JAEGER", nm, t2i(pp+", WW2 German horror, tattered shroud, glinting scope", SEED+len(J)))

print("jobs:", len(J))
for i,(g2,nm,gr) in enumerate(J):
    print("[%d/%d] %s/%s"%(i+1,len(J),g2,nm))
    try: run(g2,nm,gr)
    except Exception as e: print("  ERROR", e)
print("DONE ->", ROOT)
print("LOG COMPLETE")
