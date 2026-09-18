    .text
    .align 2
    .global pes_stadium_ball_target_branch
    .type pes_stadium_ball_target_branch, %function
// GetBallPositionBroadcast+0x150. Preserve caller-saved GPR/SIMD state and
// NZCV around the selector; x17 is the audited dead hook/branch scratch.
// Native flag/phase paths remain native outside a live Stadium update.
pes_stadium_ball_target_branch:
    sub sp, sp, #0x2c0
    stp x0, x1, [sp, #0x0]
    stp x2, x3, [sp, #0x10]
    stp x4, x5, [sp, #0x20]
    stp x6, x7, [sp, #0x30]
    stp x8, x9, [sp, #0x40]
    stp x10, x11, [sp, #0x50]
    stp x12, x13, [sp, #0x60]
    stp x14, x15, [sp, #0x70]
    stp x16, x18, [sp, #0x80]
    stp x29, x30, [sp, #0x90]
    mrs x17, nzcv
    str x17, [sp, #0xa0]
    stp q0, q1, [sp, #0xc0]
    stp q2, q3, [sp, #0xe0]
    stp q4, q5, [sp, #0x100]
    stp q6, q7, [sp, #0x120]
    stp q8, q9, [sp, #0x140]
    stp q10, q11, [sp, #0x160]
    stp q12, q13, [sp, #0x180]
    stp q14, q15, [sp, #0x1a0]
    stp q16, q17, [sp, #0x1c0]
    stp q18, q19, [sp, #0x1e0]
    stp q20, q21, [sp, #0x200]
    stp q22, q23, [sp, #0x220]
    stp q24, q25, [sp, #0x240]
    stp q26, q27, [sp, #0x260]
    stp q28, q29, [sp, #0x280]
    stp q30, q31, [sp, #0x2a0]
    mov x0, x20
    bl pes_stadium_ball_target_mode
    str w0, [sp, #0xb0]
    ldp q0, q1, [sp, #0xc0]
    ldp q2, q3, [sp, #0xe0]
    ldp q4, q5, [sp, #0x100]
    ldp q6, q7, [sp, #0x120]
    ldp q8, q9, [sp, #0x140]
    ldp q10, q11, [sp, #0x160]
    ldp q12, q13, [sp, #0x180]
    ldp q14, q15, [sp, #0x1a0]
    ldp q16, q17, [sp, #0x1c0]
    ldp q18, q19, [sp, #0x1e0]
    ldp q20, q21, [sp, #0x200]
    ldp q22, q23, [sp, #0x220]
    ldp q24, q25, [sp, #0x240]
    ldp q26, q27, [sp, #0x260]
    ldp q28, q29, [sp, #0x280]
    ldp q30, q31, [sp, #0x2a0]
    ldr x17, [sp, #0xa0]
    msr nzcv, x17
    ldp x29, x30, [sp, #0x90]
    ldp x16, x18, [sp, #0x80]
    ldp x0, x1, [sp, #0x0]
    ldp x2, x3, [sp, #0x10]
    ldp x4, x5, [sp, #0x20]
    ldp x6, x7, [sp, #0x30]
    ldp x8, x9, [sp, #0x40]
    ldp x10, x11, [sp, #0x50]
    ldp x12, x13, [sp, #0x60]
    ldp x14, x15, [sp, #0x70]
    ldr w8, [sp, #0xb0]
    add sp, sp, #0x2c0
    cbnz w8, 1f
    ldr x22, [x20, #0x1e8]
    mov w1, wzr
    adrp x17, stadium_ball_target_native_resume
    ldr x17, [x17, #:lo12:stadium_ball_target_native_resume]
    br x17
1:
    adrp x17, stadium_ball_target_live_resume
    ldr x17, [x17, #:lo12:stadium_ball_target_live_resume]
    br x17
    .size pes_stadium_ball_target_branch, .-pes_stadium_ball_target_branch
