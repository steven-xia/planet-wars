import math

# noinspection PyUnresolvedReferences
from PlanetWars import PlanetWars

# evaluation configs
STRUCTURAL_FACTOR = 10
SURROUNDING_FACTOR = 10

EXPAND_FACTOR = 2
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

    for fleet in pw.MyFleets():
        pw.GetPlanet(fleet.DestinationPlanet()).SHIPPED = True

    for planet in pw.Planets():
        if not hasattr(planet, "SHIPPED"):
            planet.SHIPPED = False


def attack_and_expand(pw):
    """
    Attack enemy planets and expand to neutral planets with all ships. Designed to come after `defend_possible()`
    because this doesn't account for possible attacks from the opponent.
    :param pw: `PlanetWars` object
    :return: None
    """

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


def do_turn(pw):
    # don't go if ...
    if len(pw.MyPlanets()) == 0 or len(pw.EnemyPlanets()) == 0:
        return

    # # don't go on the first turn.
    # if len(pw.MyPlanets()) == len(pw.EnemyPlanets()) == 1 and len(pw.MyFleets()) == len(pw.EnemyFleets()) == 0:
    #     return

    # get global turn info
    get_info(pw)

    # make moves
    defend(pw)
    attack_and_expand(pw)


def main():
    map_data = ''
    while True:
        current_line = input()
        if len(current_line) >= 2 and current_line.startswith("go"):
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
