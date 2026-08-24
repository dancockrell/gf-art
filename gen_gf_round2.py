r"""GHOST FRONT -- ART ROUND 2 (the redo list, judged by eye from round 1).

Round-1 verdicts: PENDEL / EISWITWE / CHIMAERE deaths, PANZER and JAEGER
landed on identity. The rest missed for one reason: denoise too high for
img2img (identity washed out) or txt2img underspecified (the hound came
back as a dog-headed man). Round 2 locks identity:

  * denoise 0.40-0.52 on every identity job
  * one seed per character set, so frames of one animation share a look
  * the hound is a QUADRUPED, said three ways, with bipeds in the negative

Output -> C:\Users\Admin\Downloads\gf-art\r2\<group>\<name>.png
Log    -> C:\Users\Admin\Downloads\gf-art\round2_log.txt
"""
import json, urllib.request, urllib.error, urllib.parse, time, os, sys

ROOT = r"C:\Users\Admin\Downloads\gf-art"
OUT  = os.path.join(ROOT, "r2")
LOG  = os.path.join(ROOT, "round2_log.txt")
os.makedirs(OUT, exist_ok=True)
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
 "full body visible, feet at the bottom, plain flat very dark background, "
 "no text, no watermark")
NEG=("text, letters, watermark, signature, photo, photorealistic, 3d render, "
 "blurry, lowres, cropped, multiple subjects, collage, cute, chibi, bright "
 "background, white background, frame, border, card, vignette")

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
    bo=b"----gfb"
    with open(path,"rb") as f: data=f.read()
    body=b"--"+bo+b"\r\nContent-Disposition: form-data; name=\"image\"; filename=\""+name.encode()+b"\"\r\nContent-Type: image/png\r\n\r\n"+data+b"\r\n--"+bo+b"--\r\n"
    req=urllib.request.Request(BASE+"/upload/image", data=body,
        headers={"Content-Type":"multipart/form-data; boundary="+bo.decode()})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())["name"]

def wait(pid):
    while True:
        h=json.loads(urllib.request.urlopen(BASE+"/history/"+pid, timeout=30).read())
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

def t2i(prompt, seed, neg_extra="", w=768, h=1024, steps=28, cfg=6.5):
    return {
     "1":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":CKPT}},
     "2":{"class_type":"CLIPTextEncode","inputs":{"text":STYLE+", "+prompt,"clip":["1",1]}},
     "3":{"class_type":"CLIPTextEncode","inputs":{"text":NEG+", "+neg_extra,"clip":["1",1]}},
     "4":{"class_type":"EmptyLatentImage","inputs":{"width":w,"height":h,"batch_size":1}},
     "5":{"class_type":"KSampler","inputs":{"model":["1",0],"positive":["2",0],"negative":["3",0],
          "latent_image":["4",0],"seed":seed,"steps":steps,"cfg":cfg,
          "sampler_name":"dpmpp_2m","scheduler":"karras","denoise":1.0}},
     "6":{"class_type":"VAEDecode","inputs":{"samples":["5",0],"vae":["1",2]}},
     "7":{"class_type":"SaveImage","inputs":{"images":["6",0],"filename_prefix":"gf2"}}}

def i2i(refname, prompt, seed, den=0.45, steps=32, cfg=6.0):
    return {
     "1":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":CKPT}},
     "2":{"class_type":"CLIPTextEncode","inputs":{"text":STYLE+", "+prompt,"clip":["1",1]}},
     "3":{"class_type":"CLIPTextEncode","inputs":{"text":NEG,"clip":["1",1]}},
     "L":{"class_type":"LoadImage","inputs":{"image":refname}},
     "U":{"class_type":"ImageScale","inputs":{"image":["L",0],"width":768,"height":768,
          "upscale_method":"lanczos","crop":"disabled"}},
     "E":{"class_type":"VAEEncode","inputs":{"pixels":["U",0],"vae":["1",2]}},
     "5":{"class_type":"KSampler","inputs":{"model":["1",0],"positive":["2",0],"negative":["3",0],
          "latent_image":["E",0],"seed":seed,"steps":steps,"cfg":cfg,
          "sampler_name":"dpmpp_2m","scheduler":"karras","denoise":den}},
     "6":{"class_type":"VAEDecode","inputs":{"samples":["5",0],"vae":["1",2]}},
     "7":{"class_type":"SaveImage","inputs":{"images":["6",0],"filename_prefix":"gf2"}}}

def run(group, name, graph):
    d=os.path.join(OUT, group); os.makedirs(d, exist_ok=True)
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

J=[]
def job(group,name,graph): J.append((group,name,graph))

# ---- A. HAWKEB locomotion, identity locked (one seed, den .40-.48) ------
SEED_HB=440617
HB=("exactly the same man as the reference image, identical face and clothes: "
 "dark-haired clean-shaven man, cream shirt with dark braces, rolled sleeves, "
 "orange grafted forearms, dark trousers, brown boots")
for nm,pp,dn in [
  ("idle_1", "standing at rest, weight even, arms loose", .40),
  ("idle_2", "standing at rest, weight on back foot, chest risen mid-breath", .42),
  ("run_1",  "running, right leg striding forward, arms pumping", .48),
  ("run_2",  "running, legs passing under the body", .48),
  ("run_3",  "running, left leg striding forward", .48),
  ("jump_1", "crouched low about to leap, knees deeply bent, arms swung back", .48),
  ("jump_2", "airborne mid-leap, knees tucked up", .50),
  ("jump_3", "airborne falling, legs reaching down", .50),
  ("crouch_1","kneeling on one knee, alert", .46),
  ("reload_1","standing, both hands working at a pistol at chest height", .44),
  ("reload_2","standing, driving a magazine into the pistol, elbow high", .46),
]:
    job("HAWKEB", nm, i2i(ref("HAWKEB_walk"), HB+", "+pp, SEED_HB, den=dn))

# ---- B. KNOCHEN death, from his own body (den .45/.52) ------------------
SEED_KN=440717
for nm,pp,dn in [
  ("death_1","the same armoured bone giant as the reference, buckling, knees giving way, arms dropping", .45),
  ("death_2","the same armoured bone giant as the reference, sunk to its knees, coming apart at the seams", .50),
  ("death_3","the same armoured bone giant as the reference, collapsed into a spill of bone and plate on the ground", .55),
]:
    job("KNOCHEN", nm, i2i(ref("KNOCHEN_idle"), pp, SEED_KN, den=dn))

# ---- C. TRUEMMER death, from his own body --------------------------------
SEED_TR=440817
for nm,pp,dn in [
  ("death_1","the same dozer machine as the reference, frame sagging, blade dropping to the ground", .45),
  ("death_2","the same dozer machine as the reference, spilling its heaped masonry load, tilting over", .50),
  ("death_3","the same dozer machine as the reference, collapsed dead under its own rubble heap", .55),
]:
    job("TRUEMMER", nm, i2i(ref("TRUEMMER_idle"), pp, SEED_TR, den=dn))

# ---- D. MGTEAM, keeping the emplacement and both crew --------------------
SEED_MG=440917
MG=("the same weapon emplacement as the reference: heavy machine gun behind an "
 "armoured shield plate, two helmeted crewmen, gunner and loader")
for nm,pp,dn in [
  ("fire_1", "firing, long muzzle flash, gunner braced into the grips", .44),
  ("fire_2", "firing, recoil rocking the mount, spent cases in the air", .48),
  ("reload_1","silent, loader feeding a fresh belt, gunner holding the bolt open", .46),
]:
    job("MGTEAM", nm, i2i(ref("MGTEAM_fire"), MG+", "+pp, SEED_MG, den=dn))

# ---- E. PANZERHUND, quadruped said three ways -----------------------------
SEED_PH=441017
PH=("a four-legged armoured war hound automaton, a quadruped machine beast the "
 "size of a mastiff, all four steel paws relating to the ground, low wolf-like "
 "silhouette, riveted plates along spine and skull, exposed piston haunches, "
 "red harness detail")
PHNEG=("bipedal, standing upright, two legs, human, man, soldier, humanoid, "
 "dog-headed man, werewolf, anthropomorphic, hands, arms")
for nm,pp in [
  ("idle_1", "standing alert side-on, head low"),
  ("run_1",  "galloping, forelegs reaching, hindlegs driving"),
  ("run_2",  "galloping, all four legs gathered under the body"),
  ("lunge_1","leaping fangs-first, forelegs spread"),
  ("death_1","collapsed dead on its side, legs stiff, plates scorched"),
]:
    job("PANZERHUND", nm, t2i(PH+", "+pp, SEED_PH, neg_extra=PHNEG))

# ---- F. EISWITWE attack (replaces the miscut plate) -----------------------
job("EISWITWE", "attack_1",
    i2i(ref("EISWITWE_idle"),
        "the same spider machine as the reference, rearing, front limbs raised to strike", 441117, den=.48))

print("jobs:", len(J))
for i,(g2,nm,gr) in enumerate(J):
    print("[%d/%d] %s/%s"%(i+1,len(J),g2,nm))
    try: run(g2,nm,gr)
    except Exception as e: print("  ERROR", e)
print("DONE ->", OUT)
print("LOG COMPLETE")
