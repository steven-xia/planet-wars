from __future__ import division

try:
    # noinspection PyShadowingBuiltins,PyUnresolvedReferences
    input = raw_input
except NameError:
    pass

# noinspection PyUnresolvedReferences
import PlanetWars
import math

# game configs
TOTAL_TURNS = 200
COMPETITION_MODE = True

# evaluation configs
STRUCTURAL_FACTOR = 0
SURROUNDING_FACTOR = 0
LATENCY_FACTOR = 0
CENTER_FACTOR = 0

TAKING_ENEMY_PLANETS = {}  # {planet.PlanetID(): turns_remaining}


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

    return p.GrowthRate()


def score_planet(pw, p):
    """
    Function to give a planet a score based on many factors.
    :param pw: `PlanetWars` object
    :param p: `Planet` object
    :return: `float` score of planet
    """

    raw_score = 100 * get_raw_score(p)

    structural_score = 1 - (pythag(MY_PLANETS_CENTER, (p.X(), p.Y())) / MAP_SIZE)
    # structural_score += pythag(ENEMY_PLANETS_CENTER, (p.X(), p.Y())) / MAP_SIZE

    surrounding_score = 0
    for planet in filter(lambda _p: _p != p, pw.Planets()):
        temp = (1 - (pw.Distance(p.PlanetID(), planet.PlanetID()) / MAP_SIZE)) ** 5
        surrounding_score += get_raw_score(planet) * temp
    surrounding_score /= MAP_TOTAL_GROWTH

    latency_score = p.latency / MAP_SIZE

    center_score = 1 - (pw.Distance(p.PlanetID(), 0) / MAP_SIZE)

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

    # get the size of the map
    global MAP_SIZE
    MAP_SIZE = 2 * math.ceil(pythag((0, 0), (pw.GetPlanet(0).X(), pw.GetPlanet(0).Y())))

    # get the euclidean center of my and enemy's planets
    global MY_PLANETS_CENTER, ENEMY_PLANETS_CENTER
    MY_PLANETS_CENTER = sum(map(lambda p: p.X(), pw.MyPlanets())) / len(pw.MyPlanets()), \
        sum(map(lambda p: p.Y(), pw.MyPlanets())) / len(pw.MyPlanets())
    ENEMY_PLANETS_CENTER = sum(map(lambda p: p.X(), pw.EnemyPlanets())) / len(pw.EnemyPlanets()), \
        sum(map(lambda p: p.Y(), pw.EnemyPlanets())) / len(pw.EnemyPlanets())

    # get my and enemy's total ships
    global MY_TOTAL_SHIPS, ENEMY_TOTAL_SHIPS
    MY_TOTAL_SHIPS = sum(map(lambda x: x.NumShips(), pw.MyPlanets() + pw.MyFleets()))
    ENEMY_TOTAL_SHIPS = sum(map(lambda x: x.NumShips(), pw.EnemyPlanets() + pw.EnemyFleets()))

    # get my and enemy's total growth rate
    global MY_GROWTH_RATE, ENEMY_GROWTH_RATE
    MY_GROWTH_RATE = sum(map(lambda p: p.GrowthRate(), pw.MyPlanets()))
    ENEMY_GROWTH_RATE = sum(map(lambda p: p.GrowthRate(), pw.EnemyPlanets()))

    # find which planets were "shipped"
    for fleet in pw.MyFleets():
        pw.GetPlanet(fleet.DestinationPlanet()).SHIPPED = True

    for planet in pw.Planets():
        if not hasattr(planet, "SHIPPED"):
            planet.SHIPPED = False

    # find latency of planets
    if len(pw.MyPlanets()) == 1:
        pw.MyPlanets()[0].latency = 999999
    if len(pw.EnemyPlanets()) == 1:
        pw.EnemyPlanets()[0].latency = -999999

    for planet in pw.Planets():
        if hasattr(planet, "latency"):
            continue

        closest_friend = min(filter(lambda p: p != planet, pw.MyPlanets()),
                             key=lambda p: pw.Distance(planet.PlanetID(), p.PlanetID()))
        closest_enemy = min(filter(lambda p: p != planet, pw.EnemyPlanets()),
                            key=lambda p: pw.Distance(planet.PlanetID(), p.PlanetID()))

        planet.latency = pw.Distance(closest_enemy.PlanetID(), planet.PlanetID()) - \
            pw.Distance(closest_friend.PlanetID(), planet.PlanetID())

    # global flag for if I'm dying
    global DYING
    DYING = False

    # get my and enemy's future planets
    future_planets = [{}, {}]

    pseudo_ships = {p.PlanetID(): p.NumShips() for p in pw.NeutralPlanets()}
    neutral_arriving_fleets = filter(lambda f: f.DestinationPlanet() in pseudo_ships, pw.Fleets())
    neutral_arriving_fleets = sorted(neutral_arriving_fleets, key=lambda f: f.DestinationPlanet())
    neutral_arriving_fleets = sorted(neutral_arriving_fleets, key=lambda f: f.TurnsRemaining())
    for index, fleet in enumerate(neutral_arriving_fleets):
        try:
            pseudo_ships[fleet.DestinationPlanet()] -= fleet.NumShips()
            if pseudo_ships[fleet.DestinationPlanet()] < 0 and \
                    (fleet.DestinationPlanet() != neutral_arriving_fleets[index + 1].DestinationPlanet() or
                     neutral_arriving_fleets[index + 1].TurnsRemaining() > fleet.TurnsRemaining()):
                destination_planet = pw.GetPlanet(fleet.DestinationPlanet())
                future_planets[fleet.Owner() - 1][destination_planet] = (fleet.TurnsRemaining(),
                                                                         abs(pseudo_ships[fleet.DestinationPlanet()]))
                del pseudo_ships[fleet.DestinationPlanet()]
        except IndexError:
            destination_planet = pw.GetPlanet(fleet.DestinationPlanet())
            future_planets[fleet.Owner() - 1][destination_planet] = (fleet.TurnsRemaining(),
                                                                     abs(pseudo_ships[fleet.DestinationPlanet()]))
            del pseudo_ships[fleet.DestinationPlanet()]
        except KeyError:
            pass

    global MY_FUTURE_PLANETS, ENEMY_FUTURE_PLANETS
    MY_FUTURE_PLANETS, ENEMY_FUTURE_PLANETS = future_planets

    # check if both sides are just chilling
    global CHILLING
    CHILLING = False

    for fleet in pw.Fleets():
        if fleet.Owner() == 2 and pw.GetPlanet(fleet.DestinationPlanet()).Owner() != 2:
            break
        # if fleet.Owner() != pw.GetPlanet(fleet.DestinationPlanet()).Owner():
        #     break
    else:
        CHILLING = True

    # check the result on time
    my_final_ships = MY_TOTAL_SHIPS + (TOTAL_TURNS - TURN) * MY_GROWTH_RATE
    enemy_final_ships = ENEMY_TOTAL_SHIPS + (TOTAL_TURNS - TURN) * ENEMY_GROWTH_RATE

    global TIME_RESULT
    TIME_RESULT = my_final_ships - enemy_final_ships

    # check the future result on time
    my_future_growth_rate = MY_GROWTH_RATE + sum(map(lambda p: p.GrowthRate(), MY_FUTURE_PLANETS))
    enemy_future_growth_rate = ENEMY_GROWTH_RATE + sum(map(lambda p: p.GrowthRate(), ENEMY_FUTURE_PLANETS))
    my_future_final_ships = (MY_TOTAL_SHIPS - sum(map(lambda p: p.NumShips(), MY_FUTURE_PLANETS))) + \
        (TOTAL_TURNS - TURN) * my_future_growth_rate
    enemy_future_final_ships = (ENEMY_TOTAL_SHIPS - sum(map(lambda p: p.NumShips(), ENEMY_FUTURE_PLANETS))) + \
        (TOTAL_TURNS - TURN) * enemy_future_growth_rate
    my_future_final_ships -= sum(map(lambda p: p[0].GrowthRate() * p[1][0], MY_FUTURE_PLANETS.items()))
    enemy_future_final_ships -= sum(map(lambda p: p[0].GrowthRate() * p[1][0], ENEMY_FUTURE_PLANETS.items()))

    global FUTURE_TIME_RESULT
    FUTURE_TIME_RESULT = my_future_final_ships - enemy_future_final_ships

    global MAP_TOTAL_GROWTH
    MAP_TOTAL_GROWTH = sum(map(lambda p: p.GrowthRate(), pw.Planets()))


def turn_to_take(pw, my_planet, neutral_planet):
    """
    Finds the minimum turns to take `neutral_planet` with `my_planet`.
    :param pw: `PlanetWars` object
    :param my_planet: `Planet` object
    :param neutral_planet: `Planet` object
    :return: `int` turns to take the planet
    """

    distance = pw.Distance(my_planet.PlanetID(), neutral_planet.PlanetID())
    if my_planet.NumShips() > neutral_planet.NumShips():
        return distance
    else:
        lacking_ships = neutral_planet.NumShips() - my_planet.NumShips() + 1
        ships_gain_turns = math.ceil(lacking_ships / max(my_planet.GrowthRate(), 0.01))
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
        possible_planets = filter(lambda p: not p.SHIPPED and p.latency > 0, pw.NeutralPlanets())
    sorted_planets = sorted(possible_planets, key=lambda p: score_planet(pw, p) / (p.NumShips() + 1), reverse=True)

    for attack_planet in filter(lambda p: p not in ENEMY_FUTURE_PLANETS, sorted_planets[:expand_limit]):
        quickest_planet = min(pw.MyPlanets(), key=lambda p: turn_to_take(pw, p, attack_planet))

        closest_distance = MAP_SIZE
        for enemy_planet in pw.EnemyPlanets():
            closest_distance = min(closest_distance, pw.Distance(enemy_planet.PlanetID(), attack_planet.PlanetID()))
        for enemy_planet in ENEMY_FUTURE_PLANETS:
            closest_distance = min(closest_distance, pw.Distance(enemy_planet.PlanetID(), attack_planet.PlanetID()) +
                                   ENEMY_FUTURE_PLANETS[enemy_planet][0])

        if turn_to_take(pw, quickest_planet, attack_planet) > closest_distance:
            continue

        if quickest_planet.NumShips() > attack_planet.NumShips():
            pw.IssueOrder(quickest_planet.PlanetID(), attack_planet.PlanetID(), attack_planet.NumShips() + 1)
            quickest_planet.RemoveShips(attack_planet.NumShips() + 1)
            MY_FUTURE_PLANETS[attack_planet] = (pw.Distance(quickest_planet.PlanetID(), attack_planet.PlanetID()), 1)
            attack_planet.SHIPPED = True
        else:
            quickest_planet.NumShips(0)


def defend(pw):
    """
    Defends against incoming ships ONLY. Doesn't care about any ships that might come.
    :param pw: `PlanetWars` object
    :return: None
    """

    needs_defending = []
    for planet in pw.MyPlanets():
        planet_id = planet.PlanetID()
        arriving_fleets = filter(lambda f: f.DestinationPlanet() == planet_id, pw.Fleets())
        sorted_fleets = sorted(arriving_fleets, key=lambda f: f.TurnsRemaining())

        first_oof = False
        minimum_ships_data = [planet.NumShips(), 0]
        cache_data = [planet.NumShips(), 0]  # (number of ships, turns past)
        for index, fleet in enumerate(sorted_fleets):
            cache_data[0] += planet.GrowthRate() * (fleet.TurnsRemaining() - cache_data[1])
            cache_data[0] += (-2 * fleet.Owner() + 3) * fleet.NumShips()
            cache_data[1] = fleet.TurnsRemaining()

            try:
                if cache_data[0] < minimum_ships_data[0] and sorted_fleets[index + 1].TurnsRemaining() != cache_data[1]:
                    minimum_ships_data = cache_data[:]
            except IndexError:
                # Note this is tricky logic. Above is an `and` statement, meaning the second part will only run if the
                # first part is `True`. The second part is also the only part that can cause an `IndexError` therefore,
                # we do not need to check if the first condition is `True` again.
                minimum_ships_data = cache_data[:]
            finally:
                if cache_data[0] < 0 and not first_oof:
                    first_oof = fleet.TurnsRemaining()

        if minimum_ships_data[0] < 0:
            needs_defending.append((planet, abs(minimum_ships_data[0]), minimum_ships_data[1], first_oof))
        else:
            planet.NumShips(minimum_ships_data[0])

    needs_defending_planets = frozenset(map(lambda x: x[0], needs_defending))
    needs_defending = sorted(needs_defending, key=lambda x: score_planet(pw, x[0]) / x[1], reverse=True)
    for defend_planet, defense_ships, defend_by, first_oof in needs_defending:
        for planet in pw.MyPlanets():
            if pw.Distance(planet.PlanetID(), defend_planet.PlanetID()) > defend_by or \
                    planet.NumShips() < defense_ships or \
                    planet in needs_defending_planets:
                continue
            pw.IssueOrder(planet.PlanetID(), defend_planet.PlanetID(), defense_ships)
            planet.RemoveShips(defense_ships)
            defend_planet.NumShips(0)
            break
        else:
            if first_oof == 1:
                not_death_planets = tuple(filter(lambda p: p not in needs_defending_planets, pw.MyPlanets()))
                if len(not_death_planets) > 0:
                    retreat_planet = min(not_death_planets,
                                         key=lambda p: pw.Distance(p.PlanetID(), defend_planet.PlanetID()))
                    pw.IssueOrder(defend_planet.PlanetID(), retreat_planet.PlanetID(), defend_planet.NumShips())
                    defend_planet.RemoveShips(defend_planet.NumShips())
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

    for planet in pw.MyPlanets():
        my_other_planets = filter(lambda p: p != planet, pw.MyPlanets())
        my_future_planets = filter(lambda p: pw.Distance(planet.PlanetID(), p.PlanetID()) >= MY_FUTURE_PLANETS[p][0],
                                   MY_FUTURE_PLANETS.keys())
        future_redistribute_planets = {pw.GetPlanet(p_id): t for p_id, t in TAKING_ENEMY_PLANETS.items()
                                       if pw.Distance(planet.PlanetID(), p_id) >= t}
        redistribute_planets = list(my_other_planets) + list(my_future_planets) + list(future_redistribute_planets)
        redistribute_planets = filter(lambda p: not p.dying, redistribute_planets)
        closest_planet = min(pw.EnemyPlanets() + list(ENEMY_FUTURE_PLANETS),
                             key=lambda p: pw.Distance(p.PlanetID(), planet.PlanetID()))
        for other_planet in sorted(redistribute_planets, key=lambda p: pw.Distance(closest_planet.PlanetID(),
                                                                                   p.PlanetID())):
            # attempt: fix redistribute
            # if pythag((other_planet.X(), other_planet.Y()), ENEMY_PLANETS_CENTER) > \
            #         pythag((planet.X(), planet.Y()), ENEMY_PLANETS_CENTER):
            #     continue

            redistribute_distance = pw.Distance(planet.PlanetID(), other_planet.PlanetID())
            enemy_future_planets = tuple(filter(lambda p: redistribute_distance >= ENEMY_FUTURE_PLANETS[p][0] - 1,
                                                ENEMY_FUTURE_PLANETS.keys()))
            enemy_keep_future_planets = filter(lambda p: p not in future_redistribute_planets,
                                               pw.EnemyPlanets())
            for enemy_planet in list(enemy_keep_future_planets) + list(enemy_future_planets):
                # if not (planet.X() < other_planet.X() < enemy_planet.X() or
                #         planet.X() > other_planet.X() > enemy_planet.X()) and \
                #         not (planet.Y() < other_planet.Y() < enemy_planet.Y() or
                #              planet.Y() > other_planet.Y() > enemy_planet.Y()):
                #     break

                to_enemy = pw.Distance(planet.PlanetID(), enemy_planet.PlanetID())
                if pw.Distance(planet.PlanetID(), other_planet.PlanetID()) > to_enemy or \
                        pw.Distance(other_planet.PlanetID(), enemy_planet.PlanetID()) > to_enemy:
                    break
            else:
                pw.IssueOrder(planet.PlanetID(), other_planet.PlanetID(), planet.NumShips())
                planet.RemoveShips(planet.NumShips())
                break


def defend_possible(pw):
    """
    defends against a possible all-out attack from the opponent.
    :param pw: `PlanetWars` object
    :return: None
    """

    for my_planet in pw.MyPlanets():
        furthest_planet = max(pw.Planets(), key=lambda p: pw.Distance(p.PlanetID(), my_planet.PlanetID()))
        furthest_distance = pw.Distance(furthest_planet.PlanetID(), my_planet.PlanetID())
        arriving_ships = [my_planet.GrowthRate()] * (furthest_distance + int(MAP_SIZE))

        for planet in filter(lambda p: p != my_planet, pw.MyPlanets() + pw.EnemyPlanets()):
            owner_multiplier = -2 * planet.Owner() + 3
            distance = pw.Distance(planet.PlanetID(), my_planet.PlanetID())
            arriving_ships[distance - 1] += owner_multiplier * planet.NumShips()
            for t in range(distance, len(arriving_ships)):
                arriving_ships[t] += owner_multiplier * planet.GrowthRate()

        for fleet in pw.Fleets():
            if fleet.Owner() != pw.GetPlanet(fleet.DestinationPlanet()).Owner():
                continue
            owner_multiplier = -2 * fleet.Owner() + 3
            distance = fleet.TurnsRemaining() + pw.Distance(fleet.DestinationPlanet(), my_planet.PlanetID())
            arriving_ships[distance - 1] += owner_multiplier * fleet.NumShips()

        lowest_ships = my_planet.NumShips()
        for t in range(len(arriving_ships)):
            if t >= furthest_distance:  # TODO: double check if this actually helps
                break
            lowest_ships = min(my_planet.NumShips() + sum(arriving_ships[:t]), lowest_ships)
        my_planet.NumShips(max(lowest_ships, 0))


def attack(pw):
    """
    Attacks the opponent, actually cares about defenses though.
    :param pw: `PlanetWars` object
    :return: None
    """

    enemy_planets = filter(lambda p: not p.SHIPPED, pw.EnemyPlanets())
    for enemy_planet in sorted(enemy_planets, key=lambda p: score_planet(pw, p), reverse=True):
        furthest_planet = max(pw.Planets(), key=lambda p: pw.Distance(p.PlanetID(), enemy_planet.PlanetID()))
        furthest_distance = pw.Distance(furthest_planet.PlanetID(), enemy_planet.PlanetID())
        arriving_ships = [enemy_planet.GrowthRate()] * (furthest_distance + int(MAP_SIZE))

        for planet, (turns_to_take, excess_ships) in ENEMY_FUTURE_PLANETS.items():
            distance = turns_to_take + pw.Distance(planet.PlanetID(), enemy_planet.PlanetID())
            arriving_ships[distance - 1] += excess_ships
            for t in range(distance, len(arriving_ships)):
                arriving_ships[t] += planet.GrowthRate()

        for planet in filter(lambda p: p != enemy_planet, pw.EnemyPlanets()):
            distance = pw.Distance(planet.PlanetID(), enemy_planet.PlanetID())
            arriving_ships[distance - 1] += planet.NumShips()
            for t in range(distance, len(arriving_ships)):
                arriving_ships[t] += planet.GrowthRate()

        for fleet in pw.EnemyFleets():
            if pw.GetPlanet(fleet.DestinationPlanet()).Owner() == 2:
                distance = fleet.TurnsRemaining() + pw.Distance(fleet.DestinationPlanet(), enemy_planet.PlanetID())
                arriving_ships[distance - 1] += fleet.NumShips()

        for planet in sorted(pw.MyPlanets(), key=lambda p: pw.Distance(p.PlanetID(), enemy_planet.PlanetID())):
            temp = enemy_planet.NumShips() + \
                   sum(arriving_ships[:pw.Distance(planet.PlanetID(), enemy_planet.PlanetID())])
            if planet.NumShips() > temp:
                pw.IssueOrder(planet.PlanetID(), enemy_planet.PlanetID(), temp + 1)
                planet.RemoveShips(temp + 1)
                enemy_planet.SHIPPED = True
                TAKING_ENEMY_PLANETS[enemy_planet.PlanetID()] = pw.Distance(planet.PlanetID(), enemy_planet.PlanetID())
                break

    # for taking enemy neutral planets
    enemy_planets = ENEMY_FUTURE_PLANETS
    for enemy_planet in sorted(filter(lambda p: not p.SHIPPED, enemy_planets),
                               key=lambda p: score_planet(pw, p), reverse=True):
        furthest_planet = max(pw.Planets(), key=lambda p: pw.Distance(p.PlanetID(), enemy_planet.PlanetID()))
        furthest_distance = pw.Distance(furthest_planet.PlanetID(), enemy_planet.PlanetID())
        arriving_ships = [enemy_planet.GrowthRate()] * (furthest_distance + int(MAP_SIZE))

        for planet, (turns_to_take, excess_ships) in ENEMY_FUTURE_PLANETS.items():
            if planet == enemy_planet:
                continue
            distance = turns_to_take + pw.Distance(planet.PlanetID(), enemy_planet.PlanetID())
            arriving_ships[distance - 1] += excess_ships
            for t in range(distance, len(arriving_ships)):
                arriving_ships[t] += planet.GrowthRate()

        for planet in filter(lambda p: p != enemy_planet, pw.EnemyPlanets()):
            distance = pw.Distance(planet.PlanetID(), enemy_planet.PlanetID())
            arriving_ships[distance - 1] += planet.NumShips()
            for t in range(distance, len(arriving_ships)):
                arriving_ships[t] += planet.GrowthRate()

        for fleet in pw.EnemyFleets():
            if pw.GetPlanet(fleet.DestinationPlanet()).Owner() == 2 or \
                    (pw.GetPlanet(fleet.DestinationPlanet()).Owner() == 0 and
                     fleet.TurnsRemaining() > enemy_planets[enemy_planet][0]):
                distance = fleet.TurnsRemaining() + pw.Distance(fleet.DestinationPlanet(), enemy_planet.PlanetID())
                arriving_ships[distance - 1] += fleet.NumShips()

        enemy_ships = enemy_planets[enemy_planet][1] - enemy_planets[enemy_planet][0] * enemy_planet.GrowthRate()
        for planet in sorted(pw.MyPlanets(), key=lambda p: pw.Distance(p.PlanetID(), enemy_planet.PlanetID())):
            temp = enemy_ships + \
                   sum(arriving_ships[:pw.Distance(planet.PlanetID(), enemy_planet.PlanetID())])
            if planet.NumShips() > temp and \
                    enemy_planets[enemy_planet][0] < pw.Distance(planet.PlanetID(), enemy_planet.PlanetID()):
                pw.IssueOrder(planet.PlanetID(), enemy_planet.PlanetID(), temp + 1)
                planet.RemoveShips(temp + 1)
                enemy_planet.SHIPPED = True
                TAKING_ENEMY_PLANETS[enemy_planet.PlanetID()] = pw.Distance(planet.PlanetID(), enemy_planet.PlanetID())
                break


def simple_take(pw, take_planet):
    for planet in sorted(pw.MyPlanets(), key=lambda p: pw.Distance(p.PlanetID(), take_planet.PlanetID())):
        take_ships = 1 + take_planet.NumShips() + \
                     take_planet.GrowthRate() * pw.Distance(planet.PlanetID(), take_planet.PlanetID())
        if planet.NumShips() >= take_ships:
            pw.IssueOrder(planet.PlanetID(), take_planet.PlanetID(), take_ships)
            planet.RemoveShips(take_ships)
            take_planet.SHIPPED = True
            return True
    else:
        return False


def do_turn(pw):
    global TAKING_ENEMY_PLANETS
    TAKING_ENEMY_PLANETS = {p_id: t - 1 for p_id, t in TAKING_ENEMY_PLANETS.items() if t > 1}

    # don't go if ...
    if len(pw.MyPlanets()) == 0 or len(pw.EnemyPlanets()) == 0:
        return

    # get global turn info
    get_info(pw)

    # # attempt: SPAEKAL STRATAGÉ
    # if TURN == 1:
    #     amazing_planets = filter(lambda p: 15 * p.GrowthRate() / p.NumShips() >
    #                                        pw.Distance(p.PlanetID(), pw.MyPlanets()[0].PlanetID()),
    #                              pw.NeutralPlanets())
    #     amazing_planets = filter(lambda p: p.latency > 0, amazing_planets)
    #     expand(pw, possible_planets=amazing_planets)
    #     return

    # competition_mode ;)
    if COMPETITION_MODE and CHILLING and TIME_RESULT > 0 and MY_TOTAL_SHIPS < 10 * ENEMY_TOTAL_SHIPS:
        defend_possible(pw)
        redistribute(pw)
        return

    # don't go if I'm going to win on time and too risky
    if CHILLING and TIME_RESULT > 0 and MY_TOTAL_SHIPS < ENEMY_TOTAL_SHIPS + 1000:
        # probably late middle game or endgame
        # defend_possible(pw)
        if MY_TOTAL_SHIPS > ENEMY_TOTAL_SHIPS + 100 and \
                tuple(filter(lambda f: pw.GetPlanet(f.DestinationPlanet()).Owner() == 0, pw.MyFleets())) == ():
            expand(pw, expand_limit=1)
        if MY_TOTAL_SHIPS > ENEMY_TOTAL_SHIPS + 500:
            for planet in sorted(filter(lambda p: not p.SHIPPED, pw.EnemyPlanets()), key=lambda p: p.NumShips()):
                simple_take(pw, planet)
        redistribute(pw)
        return

    # defend
    defend(pw)

    # attack!!
    attack(pw)

    # redistribute
    redistribute(pw)

    # for planet in filter(lambda p: p.latency > 0, pw.EnemyPlanets()):
    #     simple_take(pw, planet)

    # expand (if safe)
    if not DYING and FUTURE_TIME_RESULT <= 0:
        # if TURN < TOTAL_TURNS * 0.5 or not CHILLING:
        defend_possible(pw)
        expand(pw)

    redistribute(pw)


def main():
    global TURN
    TURN = 0

    pw = PlanetWars.PlanetWars()
    while True:
        current_line = input()
        if len(current_line) >= 2 and current_line.startswith("go"):
            TURN += 1
            pw.Initialise()

            do_turn(pw)
            pw.FinishTurn()

            pw = PlanetWars.PlanetWars()
        else:
            pw.ParseGameState(current_line)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('ctrl-c, leaving ...')
