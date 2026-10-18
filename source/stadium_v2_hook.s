    .text
    .align 2
    .global pes_stadium_v2_target_hook
    .type pes_stadium_v2_target_hook, %function

// ShotBroadcastBallActive + 0x6d0, after target/player prediction but before
// native ground-height, optical zoom, projection and final eye construction.
// x21=camera, x26=current GetTrans result, original sp+0x130=target Vector3.
// Every volatile GPR/SIMD register and condition/FPSR flags is preserved.
// x17 is the hook_arm64 branch scratch and not live at this verified site.
pes_stadium_v2_target_hook:
    sub sp, sp, #0x2b0
    stp x0, x1, [sp, #0x00]
    stp x2, x3, [sp, #0x10]
    stp x4, x5, [sp, #0x20]
    stp x6, x7, [sp, #0x30]
    stp x8, x9, [sp, #0x40]
    stp x10, x11, [sp, #0x50]
    stp x12, x13, [sp, #0x60]
    stp x14, x15, [sp, #0x70]
    stp x16, x17, [sp, #0x80]
    stp x18, x30, [sp, #0x90]
    mrs x16, nzcv
    mrs x17, fpsr
    stp x16, x17, [sp, #0xa0]
    stp q0, q1, [sp, #0xb0]
    stp q2, q3, [sp, #0xd0]
    stp q4, q5, [sp, #0xf0]
    stp q6, q7, [sp, #0x110]
    stp q8, q9, [sp, #0x130]
    stp q10, q11, [sp, #0x150]
    stp q12, q13, [sp, #0x170]
    stp q14, q15, [sp, #0x190]
    stp q16, q17, [sp, #0x1b0]
    stp q18, q19, [sp, #0x1d0]
    stp q20, q21, [sp, #0x1f0]
    stp q22, q23, [sp, #0x210]
    stp q24, q25, [sp, #0x230]
    stp q26, q27, [sp, #0x250]
    stp q28, q29, [sp, #0x270]
    stp q30, q31, [sp, #0x290]
    mov x0, x21
    add x1, sp, #0x3e0
    mov x2, x26
    bl pes_stadium_v2_target
    ldp q0, q1, [sp, #0xb0]
    ldp q2, q3, [sp, #0xd0]
    ldp q4, q5, [sp, #0xf0]
    ldp q6, q7, [sp, #0x110]
    ldp q8, q9, [sp, #0x130]
    ldp q10, q11, [sp, #0x150]
    ldp q12, q13, [sp, #0x170]
    ldp q14, q15, [sp, #0x190]
    ldp q16, q17, [sp, #0x1b0]
    ldp q18, q19, [sp, #0x1d0]
    ldp q20, q21, [sp, #0x1f0]
    ldp q22, q23, [sp, #0x210]
    ldp q24, q25, [sp, #0x230]
    ldp q26, q27, [sp, #0x250]
    ldp q28, q29, [sp, #0x270]
    ldp q30, q31, [sp, #0x290]
    ldp x16, x17, [sp, #0xa0]
    msr nzcv, x16
    msr fpsr, x17
    ldp x0, x1, [sp, #0x00]
    ldp x2, x3, [sp, #0x10]
    ldp x4, x5, [sp, #0x20]
    ldp x6, x7, [sp, #0x30]
    ldp x8, x9, [sp, #0x40]
    ldp x10, x11, [sp, #0x50]
    ldp x12, x13, [sp, #0x60]
    ldp x14, x15, [sp, #0x70]
    ldp x16, x17, [sp, #0x80]
    ldp x18, x30, [sp, #0x90]
    add sp, sp, #0x2b0

    // Replay displaced loads with the relocated native scalar page.
    ldr s1, [sp, #0x134]
    adrp x8, stadium_v2_height_page
    ldr x8, [x8, #:lo12:stadium_v2_height_page]
    ldr s15, [x8, #0xeb8]
    fmov s0, #4.0
    adrp x17, stadium_v2_target_resume
    ldr x17, [x17, #:lo12:stadium_v2_target_resume]
    br x17
    .size pes_stadium_v2_target_hook, .-pes_stadium_v2_target_hook
