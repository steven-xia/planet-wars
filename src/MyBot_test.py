"""
Todo:
  - Prevent redistribution on expanding planet.
  - Calculate taking enemy planets every turn using the `attack()` formula.
  - Experiment with horizon in `defend_possible()`.
  - Experiment with horizon in `expand(pw).

Todo long term:
  - Don't give up a valuable planet(s) for attacking a single planet.
  - Prioritize the battle for a large cluster over a small loner.
  - Don't expand if front line planet is not defending possible.
  - Try to stir up complications when losing on time.
  - Only expand to a planet if defensible.

normal:
cause havoc:
less cautious:
less cautious + cause havoc: 3315
less cautious + cautious cause havoc: 3325
"""

from __future__ import division

try:
    # noinspection PyShadowingBuiltins,PyUnresolvedReferences
    input = raw_input
except NameError:
    pass

# noinspection PyUnresolvedReferences
import planet_wars
import math

# game configs
COMPETITION_MODE = True

# evaluation configs
STRUCTURAL_FACTOR = 0
SURROUNDING_FACTOR = 0
LATENCY_FACTOR = 0
CENTER_FACTOR = 0

TAKING_ENEMY_PLANETS = {}  # {planet.planet_id(): turns_remaining}
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

    raw_score = 100 * get_raw_score(p)

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

    # find latency of planets
    if len(pw.my_planets()) == 1:
        pw.my_planets()[0].latency = 999999
    if len(pw.enemy_planets()) == 1:
        pw.enemy_planets()[0].latency = -999999

    for planet in pw.planets():
        if hasattr(planet, "latency"):
            continue

        closest_friend = min(filter(lambda p: p != planet, pw.my_planets()),
                             key=lambda p: pw.distance(planet.planet_id(), p.planet_id()))
        closest_enemy = min(filter(lambda p: p != planet, pw.enemy_planets()),
                            key=lambda p: pw.distance(planet.planet_id(), p.planet_id()))

        planet.latency = pw.distance(closest_enemy.planet_id(), planet.planet_id()) - \
                         pw.distance(closest_friend.planet_id(), planet.planet_id())

    # global flag for if I'm dying
    global DYING
    DYING = False


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
        ships_gain_turns = math.ceil(lacking_ships / max(my_planet.growth_rate(), 0.01))
        return distance + ships_gain_turns


def expand(pw, expand_limit=99, possible_planets=None):
    """
    Expand to neutral planets with all ships. Designed to come after `defend_possible()` because this doesn't account
    for possible attacks from the opponent.
    :param pw: `PlanetWars` object
    :param expand_limit: `int` the maximum number of planets to expand to.
    :param possible_planets: `list` of `Planet` objects, the planets to consider expanding to. None -> all
    :return: None
    """

    if possible_planets is None:
        possible_planets = filter(lambda p: not p.SHIPPED and p.latency > 0, pw.neutral_planets())
    sorted_planets = sorted(possible_planets, key=lambda p: score_planet(pw, p) / (p.num_ships() + 1), reverse=True)

    for attack_planet in filter(lambda p: p not in pw.enemy_future_neutrals, sorted_planets[:expand_limit]):
        quickest_planet = min(pw.my_planets(), key=lambda p: turn_to_take(pw, p, attack_planet))

        closest_distance = pw.map_size
        for enemy_planet in pw.enemy_planets():
            closest_distance = min(closest_distance, pw.distance(enemy_planet.planet_id(), attack_planet.planet_id()))
        for enemy_planet in pw.enemy_future_neutrals:
            closest_distance = min(closest_distance, pw.distance(enemy_planet.planet_id(), attack_planet.planet_id()) +
                                   pw.enemy_future_neutrals[enemy_planet][0])

        if turn_to_take(pw, quickest_planet, attack_planet) > closest_distance:
            continue

        if quickest_planet.num_ships() > attack_planet.num_ships():
            pw.issue_order(quickest_planet.planet_id(), attack_planet.planet_id(), attack_planet.num_ships() + 1)
            quickest_planet.remove_ships(attack_planet.num_ships() + 1)
            pw.my_future_neutrals[attack_planet] = (pw.distance(quickest_planet.planet_id(),
                                                                attack_planet.planet_id()), 1)
            attack_planet.SHIPPED = True
        else:
            quickest_planet.num_ships(0)


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
            if first_oof == 1:
                not_death_planets = tuple(filter(lambda p: p not in needs_defending_planets, pw.my_planets()))
                if len(not_death_planets) > 0:
                    retreat_planet = min(not_death_planets,
                                         key=lambda p: pw.distance(p.planet_id(), defend_planet.planet_id()))
                    pw.issue_order(defend_planet.planet_id(), retreat_planet.planet_id(), defend_planet.num_ships())
                    defend_planet.remove_ships(defend_planet.num_ships())
                defend_planet.dying = True

            global DYING
            DYING = True
            defend_planet.dying = True


def redistribute(pw):
    """
    Redistributes ships such that they are more active... well hopefully.
    :param pw: `PlanetWars` object
    :return: None
    """

    for planet in pw.my_planets():
        my_other_planets = filter(lambda p: p != planet, pw.my_planets())
        my_future_planets = filter(lambda p: pw.distance(planet.planet_id(), p.planet_id()) >=
                                             pw.my_future_neutrals[p][0],
                                   pw.my_future_neutrals.keys())
        future_redistribute_planets = {pw.get_planet(p_id): t for p_id, t in TAKING_ENEMY_PLANETS.items()
                                       if pw.distance(planet.planet_id(), p_id) >= t}
        redistribute_planets = list(my_other_planets) + list(my_future_planets) + list(future_redistribute_planets)
        redistribute_planets = filter(lambda p: not p.dying, redistribute_planets)
        closest_planet = min(pw.enemy_planets() + list(pw.enemy_future_neutrals),
                             key=lambda p: pw.distance(p.planet_id(), planet.planet_id(), raw=True))
        for other_planet in sorted(redistribute_planets, key=lambda p: pw.distance(closest_planet.planet_id(),
                                                                                   p.planet_id(), raw=True)):
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
        # for turn in range(1, pw.map_size):
        # attempt: less cautious
        for turn in range(1, round(pw.map_size / 2)):
            lowest_ships = min(sum(my_planet.my_maximum_ships[:turn]) - sum(my_planet.enemy_maximum_ships[:turn]),
                               lowest_ships)
        my_planet.num_ships(max(lowest_ships, 0))


def attack(pw):
    """
    Attacks the opponent, actually cares about defenses though.
    :param pw: `PlanetWars` object
    :return: None
    """

    enemy_planets = filter(lambda p: not p.SHIPPED, pw.enemy_planets())
    for enemy_planet in sorted(enemy_planets, key=lambda p: score_planet(pw, p), reverse=True):
        for my_planet in sorted(pw.my_planets(), key=lambda p: pw.distance(p.planet_id(), enemy_planet.planet_id())):
            needed_ships = sum(enemy_planet.enemy_maximum_ships[:pw.distance(
                my_planet.planet_id(), enemy_planet.planet_id())])
            if my_planet.num_ships() > needed_ships:
                pw.issue_order(my_planet.planet_id(), enemy_planet.planet_id(), needed_ships + 1)
                my_planet.remove_ships(needed_ships + 1)
                enemy_planet.SHIPPED = True
                TAKING_ENEMY_PLANETS[enemy_planet.planet_id()] = pw.distance(
                    my_planet.planet_id(), enemy_planet.planet_id())
                break

    # for taking enemy neutral planets
    enemy_planets = pw.enemy_future_neutrals
    for enemy_planet in sorted(filter(lambda p: not p.SHIPPED, enemy_planets),
                               key=lambda p: score_planet(pw, p), reverse=True):
        for my_planet in sorted(pw.my_planets(), key=lambda p: pw.distance(p.planet_id(), enemy_planet.planet_id())):
            needed_ships = sum(enemy_planet.enemy_maximum_ships[:pw.distance(
                my_planet.planet_id(), enemy_planet.planet_id())])
            if my_planet.num_ships() > needed_ships and \
                    enemy_planets[enemy_planet][0] < pw.distance(my_planet.planet_id(), enemy_planet.planet_id()):
                pw.issue_order(my_planet.planet_id(), enemy_planet.planet_id(), needed_ships + 1)
                my_planet.remove_ships(needed_ships + 1)
                enemy_planet.SHIPPED = True
                TAKING_ENEMY_PLANETS[enemy_planet.planet_id()] = pw.distance(
                    my_planet.planet_id(), enemy_planet.planet_id())
                break


def simple_take(pw, take_planet):
    for planet in sorted(pw.my_planets(), key=lambda p: pw.distance(p.planet_id(), take_planet.planet_id())):
        take_ships = 1 + take_planet.num_ships() + \
                     take_planet.growth_rate() * pw.distance(planet.planet_id(), take_planet.planet_id())
        if planet.num_ships() >= take_ships:
            pw.issue_order(planet.planet_id(), take_planet.planet_id(), take_ships)
            planet.remove_ships(take_ships)
            take_planet.SHIPPED = True
            return True
    else:
        return False


def cause_havoc(pw):
    global HAVOC_PLANET

    if pw.peaceful and HAVOC_PLANET[0] is None and (pw.time_result <= 0 or not COMPETITION_MODE):
        for planet in sorted(pw.enemy_planets(), key=lambda p: score_planet(pw, p), reverse=True):
            for t in range(round(pw.map_size / 2)):
                if sum(planet.my_maximum_ships[:t]) > sum(planet.enemy_maximum_ships[:t]):
                    HAVOC_PLANET = [planet.planet_id(), t + 1]
                    TAKING_ENEMY_PLANETS[planet.planet_id()] = t + 1
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
    global TAKING_ENEMY_PLANETS
    TAKING_ENEMY_PLANETS = {p_id: t - 1 for p_id, t in TAKING_ENEMY_PLANETS.items() if t > 1}

    global HAVOC_PLANET
    HAVOC_PLANET = [HAVOC_PLANET[0], HAVOC_PLANET[1] - 1] if HAVOC_PLANET[1] > 0 else [None, 0]

    # don't go if ...
    if len(pw.my_planets()) == 0 or len(pw.enemy_planets()) == 0:
        return

    # get global turn info
    get_info(pw)

    # attempt: cause havoc
    # cause_havoc(pw)

    # competition_mode ;)
    if COMPETITION_MODE and pw.chilling and pw.time_result > 0:
        redistribute(pw)
        return

    # don't go if I'm going to win on time and too risky
    if pw.chilling and pw.time_result > 0 and pw.my_total_ships < pw.enemy_total_ships + 1000:
        if pw.my_total_ships > pw.enemy_total_ships + 100 and \
                tuple(filter(lambda f: pw.get_planet(f.destination_planet()).owner() == 0, pw.my_fleets())) == ():
            expand(pw, expand_limit=1)
        if pw.my_total_ships > pw.enemy_total_ships + 500:
            for planet in sorted(filter(lambda p: not p.SHIPPED, pw.enemy_planets()), key=lambda p: p.num_ships()):
                simple_take(pw, planet)
        redistribute(pw)
        return

    # defend
    defend(pw)

    # attack!!
    attack(pw)

    # redistribute
    redistribute(pw)

    # expand (if safe)
    if not DYING and pw.time_result <= sum(map(lambda p: p.growth_rate(), pw.neutral_planets())):
        defend_possible(pw)
        expand(pw)
        redistribute(pw)

    # trade down
    if pw.chilling and pw.my_total_ships > pw.enemy_total_ships + 1000:
        for planet in sorted(filter(lambda p: not p.SHIPPED, pw.enemy_planets()), key=lambda p: p.num_ships()):
            simple_take(pw, planet)


def main():
    global TURN
    TURN = 0

    pw = planet_wars.PlanetWars()
    while True:
        current_line = input()
        if len(current_line) >= 2 and current_line.startswith("go"):
            TURN += 1
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
