r"""GHOST FRONT -- ART ROUND 3 (the redo list, judged by eye from round 1).

Round-1 verdicts: PENDEL / EISWITWE / CHIMAERE deaths, PANZER and JAEGER
landed on identity. The rest missed for one reason: denoise too high for
img2img (identity washed out) or txt2img underspecified (the hound came
back as a dog-headed man). Round 2 locks identity:

  * denoise 0.40-0.52 on every identity job
  * one seed per character set, so frames of one animation share a look
  * the hound is a QUADRUPED, said three ways, with bipeds in the negative

Output -> C:\Users\Admin\Downloads\gf-art\r2\<group>\<name>.png
Log    -> C:\Users\Admin\Downloads\gf-art\round3_log.txt
"""
import json, urllib.request, urllib.error, urllib.parse, time, os, sys

ROOT = r"C:\Users\Admin\Downloads\gf-art"
OUT  = os.path.join(ROOT, "r3")
LOG  = os.path.join(ROOT, "round3_log.txt")
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
     "7":{"class_type":"SaveImage","inputs":{"images":["6",0],"filename_prefix":"gf3"}}}

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
     "7":{"class_type":"SaveImage","inputs":{"images":["6",0],"filename_prefix":"gf3"}}}

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
def job(group,name,graph,chain=None): J.append((group,name,graph,chain))

# ---- A. HAWKEB pose frames: fresh seeds, mid denoise ----------------------
HB=("exactly the same man as the reference image, identical face and clothes: "
 "dark-haired clean-shaven man, cream shirt with dark braces, rolled sleeves, "
 "orange grafted forearms, dark trousers, brown boots")
for i,(nm,pp,dn) in enumerate([
  ("jump_1", "crouched very low, coiled to leap, knees fully bent, arms swung back behind him", .58),
  ("jump_2", "in mid-air, jumping, both feet off the ground, knees tucked up to his chest", .60),
  ("jump_3", "in mid-air, falling, legs reaching down for the ground, arms up", .60),
  ("crouch_1","kneeling down on one knee, low, one hand near the ground", .56),
  ("reload_1","standing still, head bent down, both hands together at his chest working at a pistol", .55),
  ("reload_2","standing, right elbow raised high, driving a magazine into the pistol", .56),
]):
    job("HAWKEB", nm, i2i(ref("HAWKEB_walk"), HB+", "+pp, 771001+i*37, den=dn))

# ---- B. death chains: each frame born from the last -----------------------
def chainjob(group, srcref, steps2):
    prev=None
    for i,(nm,pp,dn,sd) in enumerate(steps2):
        if prev is None:
            job(group, nm, i2i(ref(srcref), pp, sd, den=dn))
        else:
            job(group, nm, None, chain=(prev, pp, sd, dn))
        prev=nm

chainjob("KNOCHEN","KNOCHEN_idle",[
 ("death_1","the same armoured bone giant, buckling, knees bending, torso pitching forward, arms hanging",.52,772001),
 ("death_2","the same armoured bone giant fallen onto hands and knees, low, plates shedding off it",.55,772039),
 ("death_3","the same bone giant collapsed flat, a low wide horizontal spill of bones and plate on the ground",.62,772077),
])
chainjob("TRUEMMER",'TRUEMMER_idle',[
 ("death_1","the same dozer machine, frame buckled, nose tipping down, blade dug into the ground",.52,773001),
 ("death_2","the same dozer machine keeled over sideways, load spilling out",.56,773039),
 ("death_3","the same machine collapsed flat, a low horizontal heap of masonry and broken plate",.62,773077),
])

print("jobs:", len(J))
for i,(g2,nm,gr,chain) in enumerate(J):
    print("[%d/%d] %s/%s"%(i+1,len(J),g2,nm))
    try:
        if chain is not None:
            prevnm, pp, sd, dn = chain
            prevpath=os.path.join(OUT,g2,prevnm+".png")
            gr=i2i(upload(prevpath), pp, sd, den=dn)
        run(g2,nm,gr)
    except Exception as e: print("  ERROR", e)
print("DONE ->", OUT)
print("LOG COMPLETE")
