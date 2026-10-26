# Cup metal and controller footer (v88)

The supplied v87 screenshots show the winning team lifting the cup. They also
show a bright green cup and the independent native blue Next footer. These
images establish visible lifting in that reported test, without identifying
the exact shader/reflection state or establishing successful scene exit.

The prop's source base texture contains neutral metal and pale warm details.
It is not a green image. The previous cooked material uses full metallic
default-lit shading and environment reflection. V88 replaces only its material
with an explicit analytic metal approximation: the same base texture, world
normal hemisphere/key shading, a view-dependent highlight and rim. It does not
read reflection captures or add lights. This removes that environment-dependent
path; the screenshots alone do not prove why the old path became green.
Fox packed normal/specular maps remain undecoded. This is not full PC PBR.

`tools/ue_repair_cup_material.py` edits the exact Cup material in an isolated
UE4.22 project, refusing an active/source project or a resolved path escape.
The caller supplies the repository, expected ignored project, tools and report
paths through its `PESNX_CUP_MATERIAL_*` variables. No mesh or texture edit is
needed. Packaging takes only the two newly cooked Cup material sidecars;
the other twelve prop payloads, including meshes, textures and the entire
podium, are retained from the accepted package. Independent unpack, geometry/UV
export and embedded ES2/ES3.1 shader checks precede delivery.

Native WindowManager sends its Next legend through GuideBar to an independent
GuiBarWindow. Hiding the result root cannot hide that sibling. The existing live
footer callback now hides its own surface/root during ceremony ownership and
restores them afterward. It still runs the native callback and never retains
borrowed nodes or masks a guessed rectangle.

The existing custom cinematic Skip row appears only after the checked native
Start event. It uses B for a full pad, LEFT for the left horizontal Joy-Con,
and A for the right horizontal Joy-Con. Two distinct profiles show both glyphs.
The neutral-release gate and logical input mappings remain those tested in
v85. Ordinary cinematics and GoalDemo retain their existing policy.

The package also contains the optional FL26 Cup music described in
[TROPHY_AUDIO_V88.md](TROPHY_AUDIO_V88.md). Native FX methods are stubs, so PC
fireworks are not claimed or added. All 1,638 heads, 907 old heads, 436 body
selector corrections and the v87 cinematic CPK/manifest pair stay exact.

Copy the complete `switch` folder: new NRO, prop PAK, matching trophy marker
and detached music bank must travel together. Host checks do not establish the
new metal appearance, audible mix, controller Skip or final overview on Switch.
Those remain the next device test.
