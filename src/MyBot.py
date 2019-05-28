import math

# noinspection PyUnresolvedReferences
from PlanetWars import PlanetWars

# evaluation configs
STRUCTURAL_FACTOR = 20
EXPAND_FACTOR = 2
ATTACK_FACTOR = 1


def pythag(coord1, coord2):
    return math.ceil(math.sqrt((coord1[0] - coord2[0]) ** 2 + ((coord1[1] - coord2[1]) ** 2)))


def score_planet(p):
    raw_score = 100 * p.GrowthRate() / (p.NumShips() + 1)
    structural_score = 1 - pythag(MY_PLANETS_CENTER, (p.X(), p.Y())) / MAP_SIZE
    return raw_score + STRUCTURAL_FACTOR * structural_score


def get_info(pw):
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


def do_turn(pw):
    # don't go if ...
    if len(pw.MyPlanets()) == 0 or len(pw.EnemyPlanets()) == 0:
        return

    # get global turn info
    get_info(pw)

    possible_planets = filter(lambda p: not p.SHIPPED, pw.NotMyPlanets())
    sorted_planets = sorted(possible_planets, key=lambda p: score_planet(p) if p.Owner() == 0 else
                            2 * score_planet(p), reverse=True)
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
        break


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
