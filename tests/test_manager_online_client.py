"""Real async online controller against synthetic, in-process HTTP responses."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ManagerOnlineClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("gcc")
        if not compiler:
            raise unittest.SkipTest("Host C compiler unavailable")
        cls.temp = tempfile.TemporaryDirectory(prefix="manager-online-client-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.exe = cls.root / "online-client.exe"
        result = subprocess.run([
            compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I", str(ROOT / "source"), "-I", str(ROOT / "tests"), str(ROOT / "tests/test_manager_online_client.c"),
            str(ROOT / "source/manager_online_json.c"), str(ROOT / "source/loading_popup.c"),
            "-pthread", "-o", str(cls.exe),
        ], capture_output=True)
        if result.returncode:
            raise AssertionError(result.stderr.decode(errors="replace"))

    def test_every_owned_player_is_in_gameplan_and_swaps_save_then_reload(self): self.run_case("owned-plan-v118")
    def test_registration_lists_only_clubs_and_back_preserves_identity(self): self.run_case("registration-clubs-v120")
    def test_back_exits_every_hub_tab_without_logout_and_session_resumes(self): self.run_case("hub-exit-v119")
    def test_back_exits_during_background_reads_and_discards_late_results(self): self.run_case("hub-exit-background-v119")
    def test_back_dismisses_modals_and_returns_from_subpages_before_exiting(self): self.run_case("hub-exit-context-v119")
    def test_last_owned_player_remains_reachable_without_overlapping_root_buttons(self): self.run_case("owned-plan-boundary-v118")
    def test_selection_is_local_and_history_preserves_the_draft(self): self.run_case("local-selection-v117")
    def test_purchased_reserves_replace_squad_slots_and_save_in_one_request(self): self.run_case("reserves-v117")
    def test_drag_follows_the_visible_direction_on_both_axes(self): self.run_case("analog-drag-v117")
    def test_read_cache_expires_and_never_rewinds_time_or_crosses_accounts(self): self.run_case("read-cache-v117")
    def test_promotion_hides_reward_until_receipt_and_accepts_other_amounts(self): self.run_case("promotion-amount-v117")

    def test_shop_selects_club_before_sizes_and_preserves_back_focus(self): self.run_case("shop-clubs-v116")

    def test_breadcrumbs_preserve_origin_and_recover_failed_back(self): self.run_case("routes-v115")
    def test_all_time_history_validates_snapshot_without_changing_live_cache(self): self.run_case("history-v115")
    def test_unavailable_offer_is_blocked_before_any_payment(self): self.run_case("offers-v115")

    def run_case(self, mode):
        work = self.root / mode
        work.mkdir()
        # An offline save must remain untouched by authentication and purchases.
        (work / "SaveData").mkdir()
        offline = work / "SaveData/manager-league-profile-v2.dat"
        offline.write_bytes(b"synthetic offline sentinel")
        result = subprocess.run([str(self.exe), mode], cwd=work, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr).decode(errors="replace"))
        self.assertEqual(offline.read_bytes(), b"synthetic offline sentinel")

    def test_unavailable_pool_returns_to_shop_without_unpaid_intent(self): self.run_case("pool-unavailable")

    def test_pack_consent_charge_selection_grant_and_session_resume(self): self.run_case("pack")
    def test_compatibility_recheck_revokes_previous_success_on_every_failure(self): self.run_case("compat-recheck")
    def test_background_badge_allows_navigation_and_queues_foreground_actions_once(self): self.run_case("badge-navigation")
    def test_background_badge_rejects_stale_scope_and_silently_keeps_valid_cache(self): self.run_case("badge-stale")
    def test_new_cycle_or_account_clears_presentation_but_keeps_draft(self): self.run_case("cache-scope")
    def test_published_broadcast_bounds_keep_matches_accessible_despite_stale_phase_label(self): self.run_case("stale-phase")
    def test_monthly_ranking_capability_tabs_pagination_and_past_champions(self): self.run_case("monthly-ranking")
    def test_monthly_season_boundaries_leap_year_and_atomic_invalid_response_rejection(self): self.run_case("monthly-validation")
    def test_hub_live_badge_respects_phase_broadcast_bounds_freshness_and_bounded_refresh(self): self.run_case("hub-live-badge")
    def test_lost_payment_response_recovers_server_pending_without_second_post(self): self.run_case("lost-committed")
    def test_unknown_payment_survives_restart_and_blocks_another_charge(self): self.run_case("lost-not-committed")
    def test_live_uses_server_kickoff_hides_future_events_and_discards_closed_watch(self): self.run_case("watch")
    def test_test_realm_watch_accepts_authenticated_raw_chunk_arrays(self): self.run_case("test-watch")
    def test_wrong_realm_error_cannot_clear_test_redemption_recovery(self): self.run_case("wrong-realm-error")
    def test_bad_coordinates_wrong_chunks_and_future_events_fail_closed(self): self.run_case("validate")
    def test_dev_shortcut_requires_two_seconds_in_eligible_main_menu(self): self.run_case("shortcut")
    def test_json_limits_unicode_duplicates_and_uint64_bounds(self): self.run_case("json")
    def test_expired_get_refreshes_once_and_logout_removes_local_session_even_offline(self): self.run_case("auth-recovery")
    def test_incompatible_server_blocks_account_requests(self): self.run_case("gate")
    def test_selection_and_grant_lost_responses_can_be_checked_without_back_or_another_post(self): self.run_case("interrupted-selection")
    def test_dev_account_enables_api_clock_and_week_completion_without_auth_clock_jump(self): self.run_case("onlinedev")
    def test_user_id_dev_cannot_enable_test_clock_or_unadvertised_promotion(self): self.run_case("production-guard")
    def test_clock_lost_ack_survives_restart_without_advancing_twice(self): self.run_case("clock-recovery")
    def test_old_clock_receipt_reconciles_without_rolling_back_newer_bootstrap(self): self.run_case("clock-newer")
    def test_long_test_clock_job_keeps_recovery_and_releases_loading(self): self.run_case("clock-timeout")
    def test_unjoined_bootstrap_fetches_authoritative_registration_window(self): self.run_case("unjoined-open")
    def test_unjoined_during_preparation_cannot_invent_open_registration(self): self.run_case("unjoined-closed")
    def test_test_login_requires_clock_context(self): self.run_case("test-context")
    def test_bootstrap_cannot_switch_environment_or_publish_cross_realm_wallet(self): self.run_case("bootstrap-realm")
    def test_refresh_cannot_change_the_saved_session_environment(self): self.run_case("refresh-realm")
    def test_promotion_credits_authoritative_5000_receipt(self): self.run_case("promotion")
    def test_promotion_lost_ack_recovers_without_another_post(self): self.run_case("promotion-lost")
    def test_promotion_not_received_retries_exact_saved_key_and_body(self): self.run_case("promotion-retry")
    def test_invalid_code_does_not_credit_wallet(self): self.run_case("promotion-invalid")
    def test_unexpected_redemption_amount_does_not_publish_wallet(self): self.run_case("promotion-receipt")
    def test_code_validation_and_corrupt_journal_block_new_redemption(self): self.run_case("promotion-validation")
    def test_payment_journal_write_failure_never_posts_or_locks_shop(self): self.run_case("payment-write-fail")
    def test_profile_has_real_ranks_points_badge_six_submenus_and_return_focus(self): self.run_case("profile-navigation")
    def test_online_player_uses_local_portrait_binding_in_squad_and_plan(self): self.run_case("portrait-binding")
    def test_missing_calendar_is_not_a_fake_registration_or_data_error(self): self.run_case("unpublished-calendar")
    def test_completed_payment_receipt_resumes_selection_without_second_post(self): self.run_case("payment-receipt")
    def test_own_plan_edits_locally_and_saves_one_revision_on_leave(self): self.run_case("own-plan")
    def test_gameplan_lost_ack_retries_same_uuid_and_body(self): self.run_case("plan-lost")
    def test_gameplan_conflict_keeps_draft_until_explicit_discard(self): self.run_case("plan-conflict")
    def test_zero_watermark_loads_first_frame_and_reports_frozen_test_clock(self): self.run_case("watch-zero")
    def test_full_recording_fetches_once_and_hides_future_goals_until_playback(self): self.run_case("watch-bundle")
    def test_presentation_ids_hub_previews_schedule_dates_and_empty_standings(self): self.run_case("presentation")

    def test_revised_hub_join_consent_phase_gates_and_four_tile_league_tab(self): self.run_case("hub-flow")
    def test_weekly_calendar_utc7_today_countdown_and_bounded_controller_navigation(self): self.run_case("hub-calendar")
    def test_structured_activity_and_player_feeds_keep_local_identity_and_hide_future_data(self): self.run_case("hub-feed")

    def test_context_info_is_local_and_never_activates_underlying_page(self): self.run_case("context-info")
