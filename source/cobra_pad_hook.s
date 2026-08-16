    .text
    .align 2
    .global cobra_pad_update_hook
    .type cobra_pad_update_hook, %function

// Mid-function hook for cobra::game::Pad::Update + 0xd4. x19 is the Pad
// instance here. The surrounding function has no live caller-saved values
// after this point; preserve its frame/link registers, inject the current
// Switch state, replay the four overwritten instructions, then resume at +0xe4.
cobra_pad_update_hook:
    stp x29, x30, [sp, #-16]!
    mov x29, sp
    mov x0, x19
    bl cobra_pad_apply_input
    mov x17, x0
    ldp x29, x30, [sp], #16

    ldp w11, w9, [x19, #12]
    mov x8, xzr
    add x10, x19, #0x20
    bic w12, w9, w11

    br x17

    .size cobra_pad_update_hook, .-cobra_pad_update_hook

    .align 2
    .global pes_mobile_screen_tap_entry_hook
    .type pes_mobile_screen_tap_entry_hook, %function

// Entry hook for ScreenTapManager::Update. Preserve every integer argument and
// the caller frame, publish mode from the original ControlModeInfo* in x2,
// replay the four overwritten prologue instructions, and resume at +0x10.
pes_mobile_screen_tap_entry_hook:
    sub sp, sp, #0x50
    stp x0, x1, [sp, #0x00]
    stp x2, x3, [sp, #0x10]
    stp x4, x5, [sp, #0x20]
    stp x6, x7, [sp, #0x30]
    stp x29, x30, [sp, #0x40]
    ldr x0, [sp, #0x10]
    bl pes_mobile_screen_tap_entry
    mov x17, x0
    ldp x29, x30, [sp, #0x40]
    ldp x6, x7, [sp, #0x30]
    ldp x4, x5, [sp, #0x20]
    ldp x2, x3, [sp, #0x10]
    ldp x0, x1, [sp, #0x00]
    add sp, sp, #0x50

    sub sp, sp, #0x190
    stp d15, d14, [sp, #0xf0]
    stp d13, d12, [sp, #0x100]
    stp d11, d10, [sp, #0x110]
    br x17

    .size pes_mobile_screen_tap_entry_hook, .-pes_mobile_screen_tap_entry_hook

    .align 2
    .global pes_exhibition_flow_create_hook
    .type pes_exhibition_flow_create_hook, %function

// Entry hook for menu::FactoryMobile::CreateFlow. Preserve its sret pointer
// (x8) and all arguments, let C rewrite only the Divisions flow string, replay
// the displaced prologue, and continue in the original function.
pes_exhibition_flow_create_hook:
    sub sp, sp, #0x60
    stp x0, x1, [sp, #0x00]
    stp x2, x3, [sp, #0x10]
    stp x4, x5, [sp, #0x20]
    stp x6, x7, [sp, #0x30]
    str x8, [sp, #0x40]
    stp x29, x30, [sp, #0x50]
    mov x0, x1
    bl pes_exhibition_redirect_flow
    mov x17, x0
    ldp x29, x30, [sp, #0x50]
    ldr x8, [sp, #0x40]
    ldp x6, x7, [sp, #0x30]
    ldp x4, x5, [sp, #0x20]
    ldp x2, x3, [sp, #0x10]
    ldp x0, x1, [sp, #0x00]
    add sp, sp, #0x60

    sub sp, sp, #0x70
    stp x19, x30, [sp, #96]
    mov x19, x8
    and w8, w2, #1
    br x17

    .size pes_exhibition_flow_create_hook, .-pes_exhibition_flow_create_hook

    .align 2
    .global pes_exhibition_tutorial_main_hook
    .type pes_exhibition_tutorial_main_hook, %function

// Entry hook for MyClubFlowTutorialMatch::Main. The C helper changes its state
// only while a one-shot Exhibition request is armed. Preserve the original
// this pointer and caller state, replay the displaced 16-byte prologue, then
// continue at Main+0x10.
pes_exhibition_tutorial_main_hook:
    sub sp, sp, #0x50
    stp x0, x1, [sp, #0x00]
    stp x2, x3, [sp, #0x10]
    stp x4, x5, [sp, #0x20]
    stp x6, x7, [sp, #0x30]
    stp x29, x30, [sp, #0x40]
    bl pes_exhibition_tutorial_main_entry
    mov x17, x0
    ldp x29, x30, [sp, #0x40]
    ldp x6, x7, [sp, #0x30]
    ldp x4, x5, [sp, #0x20]
    ldp x2, x3, [sp, #0x10]
    ldp x0, x1, [sp, #0x00]
    add sp, sp, #0x50

    sub sp, sp, #0x70
    stp x23, x22, [sp, #64]
    stp x21, x20, [sp, #80]
    stp x19, x30, [sp, #96]
    br x17

    .size pes_exhibition_tutorial_main_hook, .-pes_exhibition_tutorial_main_hook

    .align 2
    .global pes_exhibition_strategy_main_hook
    .type pes_exhibition_strategy_main_hook, %function

// Entry hook for MyClubFlowMatchMenu::Main. The C helper seeds a master-data
// roster only for the pending custom Exhibition request. Preserve arguments,
// replay the displaced prologue, and continue at Main+0x10.
pes_exhibition_strategy_main_hook:
    sub sp, sp, #0x50
    stp x0, x1, [sp, #0x00]
    stp x2, x3, [sp, #0x10]
    stp x4, x5, [sp, #0x20]
    stp x6, x7, [sp, #0x30]
    stp x29, x30, [sp, #0x40]
    bl pes_exhibition_strategy_main_entry
    mov x17, x0
    ldp x29, x30, [sp, #0x40]
    ldp x6, x7, [sp, #0x30]
    ldp x4, x5, [sp, #0x20]
    ldp x2, x3, [sp, #0x10]
    ldp x0, x1, [sp, #0x00]
    add sp, sp, #0x50
    cbz x17, 1f

    sub sp, sp, #0x40
    stp x19, x30, [sp, #48]
    ldrb w1, [x0, #552]
    str x20, [sp, #32]
    br x17
1:
    ret

    .size pes_exhibition_strategy_main_hook, .-pes_exhibition_strategy_main_hook

    .align 2
    .global pes_exhibition_strategy_created_hook
    .type pes_exhibition_strategy_created_hook, %function

// Mid-function hook immediately after MyClubSquadEdit::CreateObject. At this
// point x19 is the Strategy flow and x1 is the new child. The helper performs
// the displaced state transition and returns the common epilogue address.
pes_exhibition_strategy_created_hook:
    stp x29, x30, [sp, #-16]!
    mov x0, x19
    bl pes_exhibition_strategy_created_entry
    mov x17, x0
    ldp x29, x30, [sp], #16
    mov w0, wzr
    br x17

    .size pes_exhibition_strategy_created_hook, .-pes_exhibition_strategy_created_hook

    .align 2
    .global pes_exhibition_training_touch_hook
    .type pes_exhibition_training_touch_hook, %function

// Entry hook for MyClubMatchTrainingTeamSelect::PadEventTouch. Record which
// of the two team panels opened the shared master-club selector.
pes_exhibition_training_touch_hook:
    sub sp, sp, #0x30
    stp x0, x1, [sp, #0x00]
    stp x2, x3, [sp, #0x10]
    stp x29, x30, [sp, #0x20]
    bl pes_exhibition_training_touch_entry
    mov x17, x0
    ldp x29, x30, [sp, #0x20]
    ldp x2, x3, [sp, #0x10]
    ldp x0, x1, [sp, #0x00]
    add sp, sp, #0x30

    sub sp, sp, #0x40
    stp x19, x30, [sp, #48]
    ldr w8, [x1, #4]
    str x20, [sp, #32]
    br x17

    .size pes_exhibition_training_touch_hook, .-pes_exhibition_training_touch_hook

    .align 2
    .global pes_exhibition_training_list_hook
    .type pes_exhibition_training_list_hook, %function

// Entry hook for SetupListInfo. Publish the selected team for the row that is
// about to be rendered before the stock COM-team formatter reads DebugMode.
pes_exhibition_training_list_hook:
    sub sp, sp, #0x40
    stp x0, x1, [sp, #0x00]
    stp x2, x3, [sp, #0x10]
    stp x29, x30, [sp, #0x30]
    bl pes_exhibition_training_list_entry
    mov x17, x0
    ldp x29, x30, [sp, #0x30]
    ldp x2, x3, [sp, #0x10]
    ldp x0, x1, [sp, #0x00]
    add sp, sp, #0x40

    stp x28, x24, [sp, #-64]!
    stp x23, x22, [sp, #16]
    stp x21, x20, [sp, #32]
    stp x19, x30, [sp, #48]
    br x17

    .size pes_exhibition_training_list_hook, .-pes_exhibition_training_list_hook

    .align 2
    .global pes_exhibition_training_child_hook
    .type pes_exhibition_training_child_hook, %function

// Capture the raw TeamId returned by MyClubFlowTeamSelect before the stock
// training window refreshes its two matchup rows.
pes_exhibition_training_child_hook:
    sub sp, sp, #0x40
    stp x0, x1, [sp, #0x00]
    stp x2, x3, [sp, #0x10]
    stp x29, x30, [sp, #0x30]
    bl pes_exhibition_training_child_entry
    mov x17, x0
    ldp x29, x30, [sp, #0x30]
    ldp x2, x3, [sp, #0x10]
    ldp x0, x1, [sp, #0x00]
    add sp, sp, #0x40

    str x20, [sp, #-32]!
    stp x19, x30, [sp, #16]
    ldrb w8, [x1]
    ldr x9, [x1, #8]
    br x17

    .size pes_exhibition_training_child_hook, .-pes_exhibition_training_child_hook

    .align 2
    .global pes_exhibition_training_footer_hook
    .type pes_exhibition_training_footer_hook, %function

// Turn Practice Match into the Exhibition hub. The helper swallows Next and
// Game Plan after handing their transition to FlowTransition::DirectSet; all
// other footer keys replay the stock function prologue.
pes_exhibition_training_footer_hook:
    sub sp, sp, #0x30
    stp x0, x1, [sp, #0x00]
    stp x2, x3, [sp, #0x10]
    stp x29, x30, [sp, #0x20]
    bl pes_exhibition_training_footer_entry
    mov x17, x0
    ldp x29, x30, [sp, #0x20]
    ldp x2, x3, [sp, #0x10]
    ldp x0, x1, [sp, #0x00]
    add sp, sp, #0x30
    cbz x17, 1f

    sub sp, sp, #0x80
    cmp w1, #3
    stp x27, x26, [sp, #48]
    stp x25, x24, [sp, #64]
    br x17
1:
    ret

    .size pes_exhibition_training_footer_hook, .-pes_exhibition_training_footer_hook

    .align 2
    .global pes_exhibition_search_post_hook
    .type pes_exhibition_search_post_hook, %function

// Tail hook for MyClubMatchSearching::UpdatePostControlWindow. The original
// state machine has finished deciding footer visibility here. Configure the
// four-button Exhibition footer, then replay the two saved-register restores
// and continue through the stock epilogue.
pes_exhibition_search_post_hook:
    sub sp, sp, #0x10
    stp x29, x30, [sp]
    mov x0, x19
    bl pes_exhibition_search_post_entry
    mov x17, x0
    ldp x29, x30, [sp]
    add sp, sp, #0x10

    ldp x19, x30, [sp, #32]
    ldp x21, x20, [sp, #16]
    br x17

    .size pes_exhibition_search_post_hook, .-pes_exhibition_search_post_hook

    .align 2
    .global pes_exhibition_search_user_name_hook
    .type pes_exhibition_search_user_name_hook, %function

// TaskMatchSearchingTraining::ActInit calls GetUserName on a nullable
// MyClubUserInfo. Ask C for either the stock string or the local Exhibition
// fallback, then replay the two string-layout loads overwritten by the
// 16-byte detour and resume after them.
pes_exhibition_search_user_name_hook:
    sub sp, sp, #0x20
    stp x29, x30, [sp, #0x00]
    mov x0, x20
    add x1, sp, #0x10
    bl pes_exhibition_search_user_name
    mov x17, x0
    ldr x0, [sp, #0x10]
    ldp x29, x30, [sp, #0x00]
    add sp, sp, #0x20

    ldrb w8, [x0]
    ldp x10, x9, [x0, #8]
    br x17

    .size pes_exhibition_search_user_name_hook, .-pes_exhibition_search_user_name_hook

    .align 2
    .global pes_exhibition_filter_teams_hook
    .type pes_exhibition_filter_teams_hook, %function

// Narrow each category vector to clubs with an installed wrapper roster. The
// original function then applies its normal availability intersection.
pes_exhibition_filter_teams_hook:
    sub sp, sp, #0x30
    stp x0, x1, [sp, #0x00]
    stp x2, x3, [sp, #0x10]
    stp x29, x30, [sp, #0x20]
    bl pes_exhibition_filter_teams_entry
    mov x17, x0
    ldp x29, x30, [sp, #0x20]
    ldp x2, x3, [sp, #0x10]
    ldp x0, x1, [sp, #0x00]
    add sp, sp, #0x30

    sub sp, sp, #0x70
    stp x28, x27, [sp, #16]
    stp x26, x25, [sp, #32]
    stp x24, x23, [sp, #48]
    br x17

    .size pes_exhibition_filter_teams_hook, .-pes_exhibition_filter_teams_hook

    .align 2
    .global pes_exhibition_string_get_hook
    .type pes_exhibition_string_get_hook, %function

// C returns a low-bit-tagged wrapper literal for Exhibition-specific labels;
// stock lookups return the aligned resume address. Untagged calls replay the
// manager's prologue and continue unchanged.
pes_exhibition_string_get_hook:
    sub sp, sp, #0x40
    stp x0, x1, [sp, #0x00]
    str x8, [sp, #0x10]
    stp x29, x30, [sp, #0x30]
    mov w0, w1
    bl pes_exhibition_string_get_target
    tbz x0, #0, 1f
    bic x0, x0, #1
    ldp x29, x30, [sp, #0x30]
    add sp, sp, #0x40
    ldp x19, x30, [sp, #32]
    ldp x21, x20, [sp, #16]
    ldr x22, [sp], #48
    ret
1:
    mov x17, x0
    ldp x29, x30, [sp, #0x30]
    ldr x8, [sp, #0x10]
    ldp x0, x1, [sp, #0x00]
    add sp, sp, #0x40

    ldr x8, [x8, #856]
    add x21, x0, #0x48
    mov x22, x0
    mov x0, x21
    br x17

    .size pes_exhibition_string_get_hook, .-pes_exhibition_string_get_hook

    .align 2
    .global pes_main_menu_simplify_hook
    .type pes_main_menu_simplify_hook, %function

// Tail hook for MyClubMain::SetupWindow. The stock Match page remains fully
// initialized so Exhibition and Training retain their native handlers, then C
// hides the unused category strip and match choices. Replay the displaced
// epilogue and return directly to the caller.
pes_main_menu_simplify_hook:
    stp x29, x30, [sp, #-16]!
    mov x29, sp
    mov x0, x19
    bl pes_main_menu_simplify
    ldp x29, x30, [sp], #16

    ldp x19, x30, [sp, #32]
    ldp x21, x20, [sp, #16]
    ldr x22, [sp], #48
    ret

    .size pes_main_menu_simplify_hook, .-pes_main_menu_simplify_hook
