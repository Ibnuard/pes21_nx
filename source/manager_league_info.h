#pragma once
/* Context help belongs in a controller-opened popup, not tiny footnotes. */
static inline const char *manager_league_page_info(MdPage page) {
  switch(page) {
    case MD_LEAGUES:case MD_CLUB:return "Choose a league, then your club identity. Registration uses club teams only. B returns to the previous selection and keeps your place.";
    case MD_DASHBOARD:return "HOME follows the current league phase. Open League Standings to visit any club. MY TEAM contains Game Plan, Player Feed, Shop and upcoming Trade History. LEAGUE contains weekly champions, monthly ranking and the guide. Select a tile and press A.";
    case MD_CLUB_PLAN:case MD_PLAN_SETTINGS:return "Substitute: scroll the right-hand list for ALL owned players. The first seven are match substitutes; the rest are reserves. Tap A to swap. Hold A + stick to drag; release to drop. B returns to the four buttons, then B saves changes to the server.";
    case MD_PLAN_RESERVES:return "Choose a reserve to replace the player focused in Game Plan. The replaced player stays in your collection. Your team has eleven starters and seven substitutes. Changes save when you leave Game Plan.";
    case MD_PURCHASE_HISTORY:return "Players from completed pack purchases appear newest first. L and R change pages of five. B returns to Shop or your unfinished pack without changing your selection.";
    case MD_WEEK_SCHEDULE:return "Each real week contains two leagues: register Monday or Thursday, prepare Tuesday or Friday, and play Wednesday or Saturday. Sunday is for results and prizes. All times use WIB (UTC+7).";
    case MD_TEAM_HISTORY:return "Completed matches from every league week appear newest first. L and R change pages, with five matches per page. A plays the selected replay. B returns to the club profile.";
    case MD_SHOP_CLUBS:case MD_SHOP:case MD_PACK:case MD_PACK_SELECT:return "Choose a club, then pack size and confirm the price. NX Cash is charged once. Select the required players to finish. A paid pack stays on the server and resumes when you reopen Shop.";
    case MD_PAYMENT_RECOVERY:return "Check Purchase asks the server about your saved request. Resume Purchase retries that exact request, keeping the same price and request ID. Your original purchase is never submitted as a second payment.";
    case MD_TEAMS_PAGE:case MD_OPPONENT_PROFILE:return "Choose a club to see its squad, saved Game Plan and match history. Opponent information uses the latest team data saved on the server.";
    case MD_OVERALL:return "Monthly Ranking adds 500 points per league joined and podium bonuses of 2,000, 1,500 or 1,000. It resets at the start of each WIB calendar month. Past Season keeps each monthly champion.";
    case MD_PLAYER_FEED:return "Top Scorers ranks goals and assists from published matches. Rising Stars highlights players rated 69 or below through their match contributions.";
    case MD_WATCH:return "The full match recording plays locally. LIVE follows the official broadcast clock; Replay can be paused and moved. Touchline lists the recorded match events at the current playback time.";
    case MD_ONLINEDEV:return "This TEST account uses a separate server clock and wallet. Demo Time runs the real league pipeline. Check Status recovers a saved operation; Resume uses the same request and cannot advance time twice.";
    case MD_PROMOTION:return "Enter a promotion code and confirm to redeem it. The reward is revealed after the server confirms redemption. Each code can be redeemed once. TEST and production codes belong to separate environments.";
    default:return "Use the left stick to move, A to open and B to return. The League Guide explains the calendar, points and prizes. Server changes are confirmed before they appear in your club.";
  }
}
