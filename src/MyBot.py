"""
Todo:
  - Test assuming that the enemy defends with ships only on the next turn.
  - Replace defensible with ships gained vs ships cost.

Todo long term:
  - Fine tune planet scoring function.
  - Only expand to a planet if defensible.
  - Defend a neutral planet that I'm taking.
  - Recognize a space advantage.
  - Attack based on minimum ships required to keep an enemy planet.
  - Expand faster when down.

Todo very long term:
  - Score moves and execute based on score.
  - Write an actual positioning function (instead of redistribute).
  - Implement minimax search.

Rating: 3370.83
"""

from __future__ import division

try:
    # noinspection PyShadowingBuiltins,PyUnresolvedReferences
    input = raw_input
except NameError:
    pass

import planet_wars
import utils

import math

__version__ = "0.8.1-dev"

# game configs
COMPETITION_MODE = True
ACCEPT_DRAWS = False

# evaluation configs
STRUCTURAL_FACTOR = 0
SURROUNDING_FACTOR = 0
LATENCY_FACTOR = 0
CENTER_FACTOR = 0

HAVOC_PLANET = [None, 0]  # [planet.planet_id(), turns_to_attack]


def pythag(coord1, coord2):
    """
    Returns the Euclidean distance between `coord1` and `coord2`. This distance is used as the actual game distance.
    :param coord1: `tuple` coordinate of the first point
    :param coord2: `tuple` coordinate of the second point
    :return: `int` distance
    """

    return math.sqrt((coord1[0] - coord2[0]) ** 2 + ((coord1[1] - coord2[1]) ** 2))


def get_raw_score(p):
    """
    Returns the basic score of the planet.
    :param p: `Planet` object
    :return: `float` score of the planet
    """

    return p.growth_rate()


def score_planet(pw, p):
    """
    Function to give a planet a score based on many factors.
    :param pw: `PlanetWars` object
    :param p: `Planet` object
    :return: `float` score of planet
    """

    raw_score = get_raw_score(p)

    structural_score = 1 - (pythag(MY_PLANETS_CENTER, (p.x(), p.y())) / pw.map_size)

    surrounding_score = 0
    for planet in filter(lambda _p: _p != p, pw.planets()):
        temp = (1 - (pw.distance(p.planet_id(), planet.planet_id()) / pw.map_size)) ** 5
        surrounding_score += get_raw_score(planet) * temp
    surrounding_score /= pw.total_growth

    latency_score = p.latency / pw.map_size

    center_score = 1 - (pw.distance(p.planet_id(), 0) / pw.map_size)

    score = 0
    score += raw_score
    score += STRUCTURAL_FACTOR * structural_score
    score += SURROUNDING_FACTOR * surrounding_score
    score += LATENCY_FACTOR * latency_score
    score += CENTER_FACTOR * center_score

    return score


def get_info(pw):
    """
    Gets basic info about the map. Saves everything in global variables.
    :param pw: `PlanetWars` object
    :return: None
    """

    # get the euclidean center of my and enemy's planets
    global MY_PLANETS_CENTER, ENEMY_PLANETS_CENTER
    MY_PLANETS_CENTER = sum(map(lambda p: p.x(), pw.my_planets())) / len(pw.my_planets()), \
                        sum(map(lambda p: p.y(), pw.my_planets())) / len(pw.my_planets())
    ENEMY_PLANETS_CENTER = sum(map(lambda p: p.x(), pw.enemy_planets())) / len(pw.enemy_planets()), \
                           sum(map(lambda p: p.y(), pw.enemy_planets())) / len(pw.enemy_planets())

    # find which planets were "shipped"
    for planet in pw.planets():
        planet.SHIPPED = False

    for fleet in pw.my_fleets():
        pw.get_planet(fleet.destination_planet()).SHIPPED = True


def furthest_meaningful_planet(pw, planet, owner):
    planets = tuple(filter(lambda p: p.owner() == owner, pw.planets()))
    fleets = tuple(filter(lambda f: f.owner() == owner, pw.fleets()))

    furthest_distance = 0
    for other_planet in planets:
        furthest_distance = max(furthest_distance, pw.distance(other_planet.planet_id(), planet.planet_id()))
    for fleet in fleets:
        furthest_distance = max(furthest_distance,
                                fleet.turns_remaining() + pw.distance(fleet.destination_planet(), planet.planet_id()))

    return furthest_distance


def turn_to_take(pw, my_planet, neutral_planet):
    """
    Finds the minimum turns to take `neutral_planet` with `my_planet`.
    :param pw: `PlanetWars` object
    :param my_planet: `Planet` object
    :param neutral_planet: `Planet` object
    :return: `int` turns to take the planet
    """

    distance = pw.distance(my_planet.planet_id(), neutral_planet.planet_id())
    if my_planet.num_ships() > neutral_planet.num_ships():
        return distance
    else:
        lacking_ships = neutral_planet.num_ships() - my_planet.num_ships() + 1
        for t in range(pw.map_size):
            lacking_ships -= my_planet.my_arriving_ships[t] + my_planet.growth_rate()
            if lacking_ships <= 0:
                break
        else:
            return 999999
        return distance + t


def return_ships(pw, planet):
    quickest_planet = min(pw.my_planets(), key=lambda p: turn_to_take(pw, p, planet))
    quickest_turns = turn_to_take(pw, quickest_planet, planet)
    return planet.growth_rate() * (pw.map_size / 2 - quickest_turns)


def defensible(pw, planet):
    quickest_planet = min(pw.my_planets(), key=lambda p: turn_to_take(pw, p, planet))
    quickest_turns = turn_to_take(pw, quickest_planet, planet)
    for t in range(quickest_turns + 1, furthest_meaningful_planet(pw, planet, 2) + 1):
        my_maximum_ships = max(0, sum(planet.my_maximum_ships[:t - 1]) - planet.num_ships() +
                               planet.growth_rate() * (t - quickest_turns))
        enemy_maximum_ships = sum(planet.enemy_maximum_ships[:t])
        if my_maximum_ships < enemy_maximum_ships:
            return False
    return True


def expand(pw, expand_limit=99, possible_planets=None, reckless=False):
    """
    Expand to neutral planets with all ships. Designed to come after `defend_possible()` because this doesn't account
    for possible attacks from the opponent.
    :param pw: `PlanetWars` object
    :param expand_limit: `int` the maximum number of planets to expand to.
    :param possible_planets: `list` of `Planet` objects, the planets to consider expanding to. None -> all
    :param reckless: `bool` whether to care about the defensibility of the planet
    :return: None
    """

    expand_limit = min(expand_limit, len(pw.neutral_planets()))

    if possible_planets is None:
        possible_planets = filter(lambda p: p not in pw.my_future_neutrals, pw.neutral_planets())

    possible_planets = filter(lambda p: p not in pw.enemy_future_neutrals, possible_planets)
    sorted_planets = sorted(
        possible_planets,
        key=lambda p: (score_planet(pw, p) - get_raw_score(p) + return_ships(pw, p)) / (p.num_ships() + 1),
        reverse=True
    )

    for _ in range(expand_limit):
        for attack_planet in sorted_planets[:expand_limit]:
            if not (attack_planet.latency > 0 and attack_planet.num_ships() < attack_planet.growth_rate()) and \
                    not reckless and not defensible(pw, attack_planet):
                continue
            # if not reckless and not defensible(pw, attack_planet):
            #     continue

            quickest_planet = min(pw.my_planets(), key=lambda p: turn_to_take(pw, p, attack_planet))

            closest_distance = pw.map_size
            for enemy_planet in pw.enemy_planets():
                closest_distance = min(closest_distance,
                                       pw.distance(enemy_planet.planet_id(), attack_planet.planet_id()))
            for enemy_planet in pw.enemy_future_neutrals:
                closest_distance = min(closest_distance,
                                       pw.distance(enemy_planet.planet_id(), attack_planet.planet_id()) +
                                       pw.enemy_future_neutrals[enemy_planet][0])

            if turn_to_take(pw, quickest_planet, attack_planet) > closest_distance:
                continue

            if quickest_planet.num_ships() > attack_planet.num_ships():
                pw.issue_order(quickest_planet.planet_id(), attack_planet.planet_id(), attack_planet.num_ships() + 1)
                quickest_planet.remove_ships(attack_planet.num_ships() + 1)
                pw.my_future_neutrals[attack_planet] = (pw.distance(quickest_planet.planet_id(),
                                                                    attack_planet.planet_id()), 1)
                attack_planet.SHIPPED = True

                for planet in pw.planets():
                    planet.my_maximum_ships[pw.distance(quickest_planet.planet_id(), planet.planet_id()) - 1] -= \
                        attack_planet.num_ships()
                    planet.my_maximum_ships[pw.distance(quickest_planet.planet_id(), attack_planet.planet_id()) +
                                            pw.distance(attack_planet.planet_id(), planet.planet_id())] += 1
                    for t in range(pw.distance(quickest_planet.planet_id(), attack_planet.planet_id()) +
                                   pw.distance(attack_planet.planet_id(), planet.planet_id()), 2 * pw.map_size):
                        planet.my_maximum_ships[t] += attack_planet.growth_rate()

                expand_limit -= 1
                sorted_planets.remove(attack_planet)
                break
            else:
                quickest_planet.num_ships(0)
                return
        else:
            break


def defend(pw):
    """
    Defends against incoming ships ONLY. Doesn't care about any ships that might come.
    :param pw: `PlanetWars` object
    :return: None
    """

    needs_defending = []
    for planet in pw.my_planets():
        planet_id = planet.planet_id()
        arriving_fleets = filter(lambda f: f.destination_planet() == planet_id, pw.fleets())
        sorted_fleets = sorted(arriving_fleets, key=lambda f: f.turns_remaining())

        first_oof = False
        minimum_ships_data = [planet.num_ships(), 0]
        cache_data = [planet.num_ships(), 0]  # (number of ships, turns past)
        for index, fleet in enumerate(sorted_fleets):
            cache_data[0] += planet.growth_rate() * (fleet.turns_remaining() - cache_data[1])
            cache_data[0] += (-2 * fleet.owner() + 3) * fleet.num_ships()
            cache_data[1] = fleet.turns_remaining()

            try:
                if cache_data[0] < minimum_ships_data[0] and \
                        sorted_fleets[index + 1].turns_remaining() != cache_data[1]:
                    minimum_ships_data = cache_data[:]
            except IndexError:
                # Note this is tricky logic. Above is an `and` statement, meaning the second part will only run if the
                # first part is `True`. The second part is also the only part that can cause an `IndexError` therefore,
                # we do not need to check if the first condition is `True` again.
                minimum_ships_data = cache_data[:]
            finally:
                if cache_data[0] < 0 and not first_oof:
                    first_oof = fleet.turns_remaining()

        if minimum_ships_data[0] < 0:
            needs_defending.append((planet, abs(minimum_ships_data[0]), minimum_ships_data[1], first_oof))
        else:
            planet.num_ships(minimum_ships_data[0])

    needs_defending_planets = frozenset(map(lambda x: x[0], needs_defending))
    needs_defending = sorted(needs_defending, key=lambda x: score_planet(pw, x[0]) / x[1], reverse=True)
    for defend_planet, defense_ships, defend_by, first_oof in needs_defending:
        for planet in pw.my_planets():
            if pw.distance(planet.planet_id(), defend_planet.planet_id()) > defend_by or \
                    planet.num_ships() < defense_ships or \
                    planet in needs_defending_planets:
                continue
            pw.issue_order(planet.planet_id(), defend_planet.planet_id(), defense_ships)
            planet.remove_ships(defense_ships)
            defend_planet.num_ships(0)
            break
        else:
            # retreat from dying planet
            if first_oof == 1:
                not_death_planets = list(filter(lambda p: p not in needs_defending_planets, pw.my_planets()))
                not_death_planets += list(filter(lambda p: pw.distance(p.planet_id(), defend_planet.planet_id()) <
                                                 pw.my_future_neutrals[p][0], pw.my_future_neutrals))
                not_death_planets += list(filter(lambda p: pw.distance(p.planet_id(), defend_planet.planet_id()) <
                                                 pw.my_future_planets[p], pw.my_future_planets))
                if len(not_death_planets) > 0:
                    retreat_planet = min(not_death_planets,
                                         key=lambda p: pw.distance(p.planet_id(), defend_planet.planet_id()))
                    pw.issue_order(defend_planet.planet_id(), retreat_planet.planet_id(), defend_planet.num_ships())
                    defend_planet.remove_ships(defend_planet.num_ships())


def redistribute(pw):
    """
    Redistributes ships such that they are more active... well hopefully.
    :param pw: `PlanetWars` object
    :return: None
    """

    for planet in filter(lambda p: p.num_ships() > 0, pw.my_planets()):
        my_other_planets = filter(lambda p: p != planet, pw.my_planets())
        my_future_planets = filter(lambda p: pw.distance(planet.planet_id(), p.planet_id()) >=
                                             pw.my_future_neutrals[p][0],
                                   pw.my_future_neutrals.keys())
        future_redistribute_planets = {p: t for p, t in pw.my_future_planets.items()
                                       if pw.distance(planet.planet_id(), p.planet_id()) >= t}
        redistribute_planets = list(my_other_planets) + list(my_future_planets) + list(future_redistribute_planets)
        redistribute_planets = filter(lambda p: p not in pw.enemy_future_planets, redistribute_planets)
        closest_planet = min(pw.enemy_planets() + list(pw.enemy_future_neutrals) + list(pw.enemy_future_planets),
                             key=lambda p: pw.distance(p.planet_id(), planet.planet_id(), raw=True))
        for other_planet in sorted(redistribute_planets, key=lambda p: pw.distance(closest_planet.planet_id(),
                                                                                   p.planet_id(), raw=True)):
            if pw.distance(planet.planet_id(), closest_planet.planet_id(), raw=True) <= \
                    pw.distance(other_planet.planet_id(), closest_planet.planet_id(), raw=True):
                break

            redistribute_distance = pw.distance(planet.planet_id(), other_planet.planet_id(), raw=True)
            enemy_future_planets = tuple(filter(lambda p: redistribute_distance >= pw.enemy_future_neutrals[p][0] - 1,
                                                pw.enemy_future_neutrals.keys()))
            enemy_keep_future_planets = filter(lambda p: p not in future_redistribute_planets,
                                               pw.enemy_planets())
            for enemy_planet in filter(lambda p: pw.distance(p.planet_id(), planet.planet_id()) < pw.map_size / 2,
                                       list(enemy_keep_future_planets) + list(enemy_future_planets)):
                # if not (planet.x() < other_planet.x() < enemy_planet.x() or
                #         planet.x() > other_planet.x() > enemy_planet.x()) and \
                #         not (planet.y() < other_planet.y() < enemy_planet.y() or
                #              planet.y() > other_planet.y() > enemy_planet.y()):
                #     break

                to_enemy = pw.distance(planet.planet_id(), enemy_planet.planet_id(), raw=True)
                if pw.distance(planet.planet_id(), other_planet.planet_id(), raw=True) > to_enemy or \
                        pw.distance(other_planet.planet_id(), enemy_planet.planet_id(), raw=True) > to_enemy:
                    break
            else:
                pw.issue_order(planet.planet_id(), other_planet.planet_id(), planet.num_ships())
                planet.remove_ships(planet.num_ships())
                break


def defend_possible(pw):
    """
    defends against a possible all-out attack from the opponent.
    :param pw: `PlanetWars` object
    :return: None
    """

    for my_planet in pw.my_planets():
        lowest_ships = my_planet.num_ships()
        for turn in range(1, furthest_meaningful_planet(pw, my_planet, 2) + 1):
            lowest_ships = min(sum(my_planet.my_maximum_ships[:turn]) - sum(my_planet.enemy_maximum_ships[:turn]),
                               lowest_ships)
        my_planet.num_ships(max(lowest_ships, 0))


def attack(pw):
    """
    Attacks the opponent, actually cares about defenses though.
    :param pw: `PlanetWars` object
    :return: None
    """

    enemy_planets = filter(lambda p: p not in pw.my_future_planets, pw.enemy_planets())
    for enemy_planet in sorted(enemy_planets, key=lambda p: score_planet(pw, p), reverse=True):
        for my_planet in sorted(pw.my_planets(), key=lambda p: pw.distance(p.planet_id(), enemy_planet.planet_id())):
            needed_ships = sum(enemy_planet.enemy_maximum_ships[:pw.distance(
                my_planet.planet_id(), enemy_planet.planet_id())]) - \
                           sum(enemy_planet.my_arriving_ships[:pw.distance(
                               my_planet.planet_id(), enemy_planet.planet_id())])
            if my_planet.num_ships() > needed_ships:
                pw.issue_order(my_planet.planet_id(), enemy_planet.planet_id(), needed_ships + 1)
                my_planet.remove_ships(needed_ships + 1)
                enemy_planet.SHIPPED = True
                pw.my_future_planets[enemy_planet] = pw.distance(
                    my_planet.planet_id(), enemy_planet.planet_id())
                break

    # for taking enemy neutral planets
    enemy_planets = pw.enemy_future_neutrals
    for enemy_planet in sorted(filter(lambda p: p not in pw.my_future_planets, enemy_planets),
                               key=lambda p: score_planet(pw, p), reverse=True):
        for my_planet in sorted(pw.my_planets(), key=lambda p: pw.distance(p.planet_id(), enemy_planet.planet_id())):
            needed_ships = sum(enemy_planet.enemy_maximum_ships[:pw.distance(
                my_planet.planet_id(), enemy_planet.planet_id())])
            if my_planet.num_ships() > needed_ships and \
                    enemy_planets[enemy_planet][0] < pw.distance(my_planet.planet_id(), enemy_planet.planet_id()):
                pw.issue_order(my_planet.planet_id(), enemy_planet.planet_id(), needed_ships + 1)
                my_planet.remove_ships(needed_ships + 1)
                enemy_planet.SHIPPED = True
                pw.my_future_planets[enemy_planet] = pw.distance(
                    my_planet.planet_id(), enemy_planet.planet_id())
                break


def simple_take(pw, take_planet):
    for planet in sorted(pw.my_planets(), key=lambda p: pw.distance(p.planet_id(), take_planet.planet_id())):
        take_ships = 1 + take_planet.num_ships() + \
                     take_planet.growth_rate() * pw.distance(planet.planet_id(), take_planet.planet_id()) + \
                     sum(planet.enemy_arriving_ships[:pw.distance(planet.planet_id(), take_planet.planet_id())])
        if planet.num_ships() >= take_ships:
            pw.issue_order(planet.planet_id(), take_planet.planet_id(), take_ships)
            planet.remove_ships(take_ships)
            take_planet.SHIPPED = True
            return True
    else:
        return False


def cause_havoc(pw):
    global HAVOC_PLANET

    if pw.peaceful and HAVOC_PLANET[0] is None and (pw.time_result <= -ACCEPT_DRAWS or not COMPETITION_MODE):
        for planet in sorted(filter(lambda p: p not in pw.my_future_planets, pw.enemy_planets()),
                             key=lambda p: score_planet(pw, p), reverse=True):
            for t in range(furthest_meaningful_planet(pw, planet, 1) + 1):
                if sum(planet.my_maximum_ships[:t]) > sum(planet.enemy_maximum_ships[:t]):
                    HAVOC_PLANET = [planet.planet_id(), t]
                    break
            if HAVOC_PLANET[0] is not None:
                break

    if HAVOC_PLANET[0] is not None:
        for planet in filter(lambda p: pw.distance(p.planet_id(), HAVOC_PLANET[0]) == HAVOC_PLANET[1], pw.my_planets()):
            pw.issue_order(planet.planet_id(), HAVOC_PLANET[0], planet.num_ships())
            planet.remove_ships(planet.num_ships())
        for planet in filter(lambda p: pw.distance(p.planet_id(), HAVOC_PLANET[0]) < HAVOC_PLANET[1], pw.my_planets()):
            planet.num_ships(0)


def do_turn(pw):
    global HAVOC_PLANET
    HAVOC_PLANET = [HAVOC_PLANET[0], HAVOC_PLANET[1] - 1] if HAVOC_PLANET[1] > 0 else [None, 0]

    # don't go if ...
    if len(pw.my_planets()) == 0:
        return

    if len(pw.enemy_planets()) == 0:
        defend(pw)
        attack(pw)
        return

    # get global turn info
    get_info(pw)

    # competition_mode ;)
    if COMPETITION_MODE and pw.chilling and pw.time_result > -ACCEPT_DRAWS:
        redistribute(pw)
        return

    # cause havoc!
    cause_havoc(pw)

    # defend
    defend(pw)

    # attack!!
    attack(pw)

    # first redistribute
    redistribute(pw)

    # expand (if losing)
    if pw.turn > pw.map_size and pw.chilling and pw.time_result <= -ACCEPT_DRAWS:
        for l in range(pw.map_size):
            expand(pw, expand_limit=1, possible_planets=filter(lambda p: p.latency > -l, pw.neutral_planets()),
                   reckless=True)
            for planet in pw.neutral_planets():
                if planet.SHIPPED:
                    break
            else:
                continue
            break

    # expand (if safe)
    if pw.enemy_future_planets == {} and pw.time_result <= sum(map(lambda p: p.growth_rate(), pw.neutral_planets())):
        defend_possible(pw)
        expand(pw)
    elif pw.chilling and pw.turn > pw.map_size:
        defend_possible(pw)
        expand(pw, expand_limit=1)

    redistribute(pw)

    # trade down
    if pw.chilling and pw.my_total_ships > pw.enemy_total_ships + 1000:
        for planet in sorted(filter(lambda p: not p.SHIPPED, pw.enemy_planets()), key=lambda p: p.num_ships()):
            simple_take(pw, planet)


def main():
    pw = planet_wars.PlanetWars()
    while True:
        current_line = input()
        if len(current_line) >= 2 and current_line.startswith("go"):
            pw.initialise()

            do_turn(pw)
            pw.finish_turn()

            pw = planet_wars.PlanetWars()
        else:
            pw.parse_game_state(current_line)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('ctrl-c, leaving ...')
