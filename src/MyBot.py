import math

# noinspection PyUnresolvedReferences
from PlanetWars import PlanetWars

# evaluation configs
STRUCTURAL_FACTOR = 10
SURROUNDING_FACTOR = 10

EXPAND_FACTOR = 1
ATTACK_FACTOR = 1


def pythag(coord1, coord2):
    """
    Returns the Euclidean distance between `coord1` and `coord2`. This distance is used as the actually game distance.
    :param coord1: `tuple` coordinate of the first point
    :param coord2: `tuple` coordinate of the second point
    :return: `int` distance
    """

    return math.ceil(math.sqrt((coord1[0] - coord2[0]) ** 2 + ((coord1[1] - coord2[1]) ** 2)))


def score_planet(pw, p, number_ships=None):
    """
    Function to give a planet a score based on many factors.
    :param pw: `PlanetWars` object
    :param p: `Planet` object
    :param number_ships: `int` the cost of the planet in ships. Will be automatically calculated if not supplied.
    :return: `float` score of planet
    """

    if number_ships is None:
        number_ships = p.NumShips()

    raw_score = 100 * p.GrowthRate() / (number_ships + 1)
    structural_score = 1 - (pythag(MY_PLANETS_CENTER, (p.X(), p.Y())) / MAP_SIZE)
    structural_score += pythag(ENEMY_PLANETS_CENTER, (p.X(), p.Y())) / MAP_SIZE

    surrounding_score = 0
    for planet in filter(lambda _p: _p != p, pw.Planets()):
        temp = (1 - (pw.Distance(p.PlanetID(), planet.PlanetID()) / MAP_SIZE)) ** 10
        surrounding_score += p.GrowthRate() * temp

    return raw_score + STRUCTURAL_FACTOR * structural_score + SURROUNDING_FACTOR * surrounding_score


def get_info(pw):
    """
    Gets basic info about the map. Saves everything in global variables.
    :param pw: `PlanetWars` object
    :return: None
    """

    global MAP_SIZE
    MAP_SIZE = 2 * pythag((0, 0), (pw.GetPlanet(0).X(), pw.GetPlanet(0).Y()))

    global MY_PLANETS_CENTER, ENEMY_PLANETS_CENTER
    MY_PLANETS_CENTER = sum(map(lambda p: p.X(), pw.MyPlanets())) / len(pw.MyPlanets()), \
        sum(map(lambda p: p.Y(), pw.MyPlanets())) / len(pw.MyPlanets())
    ENEMY_PLANETS_CENTER = sum(map(lambda p: p.X(), pw.EnemyPlanets())) / len(pw.EnemyPlanets()), \
        sum(map(lambda p: p.Y(), pw.EnemyPlanets())) / len(pw.EnemyPlanets())

    global MY_TOTAL_SHIPS, ENEMY_TOTAL_SHIPS
    MY_TOTAL_SHIPS = sum(map(lambda x: x.NumShips(), pw.MyPlanets() + pw.MyFleets()))
    ENEMY_TOTAL_SHIPS = sum(map(lambda x: x.NumShips(), pw.EnemyPlanets() + pw.EnemyFleets()))

    global MY_GROWTH_RATE, ENEMY_GROWTH_RATE
    MY_GROWTH_RATE = sum(map(lambda p: p.GrowthRate(), pw.MyPlanets()))
    ENEMY_GROWTH_RATE = sum(map(lambda p: p.GrowthRate(), pw.EnemyPlanets()))

    # global MY_FRONTLINE_PLANETS, ENEMY_FRONTLINE_PLANETS

    for fleet in pw.MyFleets():
        pw.GetPlanet(fleet.DestinationPlanet()).SHIPPED = True

    for planet in pw.Planets():
        if not hasattr(planet, "SHIPPED"):
            planet.SHIPPED = False

    if len(pw.MyPlanets()) == 1:
        pw.MyPlanets()[0].latency = 999999
    if len(pw.EnemyPlanets()) == 1:
        pw.EnemyPlanets()[0].latency = 999999

    for planet in pw.Planets():
        if hasattr(planet, "latency"):
            continue

        closest_friend = min(filter(lambda p: p != planet, pw.MyPlanets()),
                             key=lambda p: pw.Distance(planet.PlanetID(), p.PlanetID()))
        closest_enemy = min(filter(lambda p: p != planet, pw.EnemyPlanets()),
                            key=lambda p: pw.Distance(planet.PlanetID(), p.PlanetID()))

        planet.latency = pw.Distance(closest_enemy.PlanetID(), planet.PlanetID()) - \
            pw.Distance(closest_friend.PlanetID(), planet.PlanetID())


def attack_and_expand(pw, possible_planets=None):
    """
    Attack enemy planets and expand to neutral planets with all ships. Designed to come after `defend_possible()`
    because this doesn't account for possible attacks from the opponent.
    :param pw: `PlanetWars` object
    :param possible_planets: `list` with `Planet`s inside of planets to consider.
    :return: None
    """

    if possible_planets is None:
        possible_planets = filter(lambda p: not p.SHIPPED, pw.NotMyPlanets())

    sorted_planets = sorted(possible_planets, key=lambda p: score_planet(pw, p) if p.Owner() == 0 else
                            2 * score_planet(pw, p), reverse=True)
    for attack_planet in sorted_planets:
        for planet in sorted(pw.MyPlanets(), key=lambda p: pw.Distance(p.PlanetID(), attack_planet.PlanetID())):
            defense_ships = attack_planet.NumShips() if attack_planet.Owner() == 0 else \
                attack_planet.NumShips() + \
                attack_planet.GrowthRate() * pw.Distance(attack_planet.PlanetID(), planet.PlanetID())

            if (attack_planet.Owner() == 0 and planet.NumShips() > EXPAND_FACTOR * defense_ships) or \
                    (attack_planet.Owner() == 2 and planet.NumShips() > ATTACK_FACTOR * defense_ships):
                break
        else:
            continue

        pw.IssueOrder(planet.PlanetID(), attack_planet.PlanetID(), defense_ships + 1)
        planet.RemoveShips(defense_ships + 1)
        attack_planet.SHIPPED = True
        break


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

        if minimum_ships_data[0] < 0:
            needs_defending.append((planet, abs(minimum_ships_data[0]), minimum_ships_data[1]))
        else:
            planet.NumShips(minimum_ships_data[0])

    needs_defending_planets = frozenset(map(lambda x: x[0], needs_defending))
    needs_defending = sorted(needs_defending, key=lambda x: score_planet(pw, x[0], x[1]), reverse=True)
    for defend_planet, defense_ships, defend_by in needs_defending:
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
            if defend_by == 1:
                not_death_planets = tuple(filter(lambda p: p not in needs_defending_planets, pw.MyPlanets()))
                if len(not_death_planets) > 0:
                    retreat_planet = min(not_death_planets,
                                         key=lambda p: pw.Distance(p.PlanetID(), defend_planet.PlanetID()))
                    pw.IssueOrder(defend_planet.PlanetID(), retreat_planet.PlanetID(), defend_planet.NumShips())
                    defend_planet.RemoveShips(defend_planet.NumShips())


def redistribute(pw):
    """
    Redistributes ships such that they are more active... well hopefully.
    :param pw: `PlanetWars` object
    :return: None
    """

    for planet in pw.MyPlanets():
        for other_planet in sorted(filter(lambda p: p != planet, pw.MyPlanets()),
                                   key=lambda p: pw.Distance(planet.PlanetID(), p.PlanetID())):  # , reverse=True):
            # redistribute_distance = pw.Distance(planet.PlanetID(), other_planet.PlanetID())
            for enemy_planet in pw.EnemyPlanets():
                # if (not planet.X() < other_planet.X() < enemy_planet.X() and
                #         not planet.X() > other_planet.X() > enemy_planet.X()) or \
                #         (not planet.Y() < other_planet.Y() < enemy_planet.Y() and
                #          not planet.Y() > other_planet.Y() > enemy_planet.Y()):
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
        # pseudo_ships = {p.PlanetID(): p.NumShips() for p in pw.NeutralPlanets()}

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
            arriving_ships[distance] += owner_multiplier * fleet.NumShips()

        lowest_ships = my_planet.NumShips()
        for t in range(len(arriving_ships)):
            lowest_ships = min(my_planet.NumShips() + sum(arriving_ships[:t]), lowest_ships)
        my_planet.NumShips(max(lowest_ships, 0))


def attack(pw):
    """
    Attacks the opponent, actually cares about defenses though.
    :param pw: `PlanetWars` object
    :return: None
    """

    for enemy_planet in sorted(pw.EnemyPlanets(), key=lambda p: score_planet(pw, p), reverse=True):
        furthest_planet = max(pw.Planets(), key=lambda p: pw.Distance(p.PlanetID(), enemy_planet.PlanetID()))
        furthest_distance = pw.Distance(furthest_planet.PlanetID(), enemy_planet.PlanetID())
        arriving_ships = [enemy_planet.GrowthRate()] * (furthest_distance + int(MAP_SIZE))
        # pseudo_ships = {p.PlanetID(): p.NumShips() for p in pw.NeutralPlanets()}

        for planet in filter(lambda p: p != enemy_planet, pw.EnemyPlanets()):
            distance = pw.Distance(planet.PlanetID(), enemy_planet.PlanetID())
            arriving_ships[distance - 1] += planet.NumShips()
            for t in range(distance, len(arriving_ships)):
                arriving_ships[t] += planet.GrowthRate()

        for fleet in pw.EnemyFleets():
            if fleet.Owner() != pw.GetPlanet(fleet.DestinationPlanet()).Owner():
                continue
            distance = fleet.TurnsRemaining() + pw.Distance(fleet.DestinationPlanet(), enemy_planet.PlanetID())
            arriving_ships[distance] += fleet.NumShips()

        for planet in sorted(pw.MyPlanets(), key=lambda p: pw.Distance(p.PlanetID(), enemy_planet.PlanetID())):
            temp = enemy_planet.NumShips() + \
                   sum(arriving_ships[:pw.Distance(planet.PlanetID(), enemy_planet.PlanetID())])
            if planet.NumShips() > temp:
                pw.IssueOrder(planet.PlanetID(), enemy_planet.PlanetID(), temp + 1)
                planet.RemoveShips(temp + 1)
                enemy_planet.SHIPPED = True
                break


def do_turn(pw):
    # don't go if ...
    if len(pw.MyPlanets()) == 0 or len(pw.EnemyPlanets()) == 0:
        return

    # get global turn info
    get_info(pw)

    # attack!!
    attack(pw)

    # defend
    if TURN < 40 or ENEMY_TOTAL_SHIPS < 2 * MY_TOTAL_SHIPS:
        defend(pw)

    # defend for possible ships
    if TURN < 40 or ENEMY_TOTAL_SHIPS <= 1.2 * MY_TOTAL_SHIPS:
        defend_possible(pw)

    # attack
    if TURN > 20 or 2 * ENEMY_TOTAL_SHIPS < MY_TOTAL_SHIPS:
        attack_planets = filter(lambda p: not p.SHIPPED and p.latency > 0, pw.EnemyPlanets())
        attack_and_expand(pw, attack_planets)

    # expand
    attack_planets = filter(lambda p: not p.SHIPPED and p.latency > 0, pw.NeutralPlanets())
    attack_and_expand(pw, attack_planets)

    # redistribute
    redistribute(pw)


def main():
    global TURN
    TURN = 0

    map_data = ''
    while True:
        current_line = input()
        if len(current_line) >= 2 and current_line.startswith("go"):
            TURN += 1

            pw = PlanetWars(map_data)
            do_turn(pw)
            pw.FinishTurn()
            map_data = ''
        else:
            map_data += current_line + '\n'


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('ctrl-c, leaving ...')
