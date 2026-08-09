    .text
    .align 2
    .global ue4_tickrate_clamp_hook
    .type ue4_tickrate_clamp_hook, %function

// Mid-function hook for UEngine::UpdateTimeAndHandleMaxTickRate +0x2bc.
// x19 is the UEngine instance and s0 contains GetMaxTickRate's effective value.
// Preserve s0 across the C helper, replay the optional FixedFrameRate override,
// then clamp only a positive effective rate below 30 FPS.
ue4_tickrate_clamp_hook:
    sub sp, sp, #32
    stp x29, x30, [sp]
    str q0, [sp, #16]
    mov x29, sp
    mov x0, x19
    bl ue4_tickrate_clamp
    mov x17, x0
    ldr q0, [sp, #16]
    ldp x29, x30, [sp]
    add sp, sp, #32

    ldrb w8, [x19, #1920]
    tbz w8, #6, 1f
    ldr s0, [x19, #1924]
1:
    fcmp s0, #0.0
    b.le 2f
    fmov s1, #30.0
    fcmp s0, s1
    fcsel s0, s1, s0, lt
2:
    fcmp s0, #0.0
    br x17

    .size ue4_tickrate_clamp_hook, .-ue4_tickrate_clamp_hook

    .align 2
    .global pes_virtual_pad_update_original
    .type pes_virtual_pad_update_original, %function
pes_virtual_pad_update_original:
    sub sp, sp, #0xe0
    str d10, [sp, #96]
    stp d9, d8, [sp, #112]
    stp x28, x27, [sp, #128]
    adrp x17, pes_virtual_pad_update_resume
    ldr x17, [x17, :lo12:pes_virtual_pad_update_resume]
    br x17
    .size pes_virtual_pad_update_original, .-pes_virtual_pad_update_original
