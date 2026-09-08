#ifndef PES21_EXPERIMENTAL_INTER_MIAMI_H
#define PES21_EXPERIMENTAL_INTER_MIAMI_H

#include <stdint.h>

#ifndef PES_EXPERIMENT_INTER_MIAMI
#define PES_EXPERIMENT_INTER_MIAMI 1
#endif

#if PES_EXPERIMENT_INTER_MIAMI
#define EXHIBITION_INTER_MIAMI_LOGICAL_TEAM_ID 5738u
#define EXHIBITION_INTER_MIAMI_PHYSICAL_TEAM_ID 2473u

static const uint32_t experimental_inter_miami_players[] = {
    34430u,  109842u, 118960u, 127201u, 153007u, 38568u,  160365u,
    157971u, 152391u, 7511u,   34881u,  135359u, 142912u, 145651u,
    152772u, 160151u, 143641u, 40425u,  144296u, 160784u, 142972u,
    104790u, 168915u, 163647u, 160362u, 168129u, 166137u,
};

static const uint8_t experimental_inter_miami_shirts[] = {
    18u, 36u, 13u, 56u, 31u, 4u,  29u, 7u,  20u,
    9u,  8u,  33u, 0u,  16u, 14u, 5u,  1u,  17u,
    54u, 40u, 23u, 6u,  21u, 25u, 61u, 41u, 80u,
};

static uint32_t experimental_inter_miami_portrait_id(uint32_t player_id) {
  switch (player_id) {
  case 34430u:
    return 34938u;
  case 104790u:
    return 104858u;
  case 142912u:
    return 141464u;
  case 142972u:
    return 140711u;
  case 143641u:
    return 141611u;
  case 144296u:
    return 141634u;
  case 145651u:
    return 141563u;
  case 152391u:
    return 141094u;
  case 152772u:
    return 141208u;
  case 153007u:
    return 141552u;
  case 157971u:
    return 141406u;
  case 160151u:
    return 141195u;
  case 160362u:
    return 141453u;
  case 160365u:
    return 141513u;
  case 160784u:
    return 141577u;
  case 163647u:
    return 141174u;
  case 166137u:
    return 141578u;
  case 168129u:
    return 141543u;
  case 168915u:
    return 141483u;
  default:
    return player_id;
  }
}

#endif

#endif
