import sys

import math

import utils


TOTAL_TURNS = 200


class Fleet:
    def __init__(self, owner, num_ships, source_planet, destination_planet,
                 total_trip_length, turns_remaining):
        self._owner = owner
        self._num_ships = num_ships
        self._source_planet = source_planet
        self._destination_planet = destination_planet
        self._total_trip_length = total_trip_length
        self._turns_remaining = turns_remaining

    def owner(self):
        return self._owner

    def num_ships(self):
        return self._num_ships

    def source_planet(self):
        return self._source_planet

    def destination_planet(self):
        return self._destination_planet

    def total_trip_length(self):
        return self._total_trip_length

    def turns_remaining(self):
        return self._turns_remaining


class Planet:
    def __init__(self, planet_id, owner, num_ships, growth_rate, x, y):
        self._planet_id = planet_id
        self._owner = owner
        self._num_ships = num_ships
        self._growth_rate = growth_rate
        self._x = x
        self._y = y

        self.dying = False

    def planet_id(self):
        return self._planet_id

    def owner(self, new_owner=None):
        if new_owner is None:
            return self._owner
        self._owner = new_owner

    def num_ships(self, new_num_ships=None):
        if new_num_ships is None:
            return self._num_ships
        self._num_ships = new_num_ships

    def growth_rate(self):
        return self._growth_rate

    def x(self):
        return self._x

    def y(self):
        return self._y

    def add_ships(self, amount):
        self._num_ships += amount

    def remove_ships(self, amount):
        self._num_ships -= amount


class PlanetWars:
    turn = 0

    def __init__(self):
        self._planets = []
        self._fleets = []

        self._planet_id_counter = 0
        self._temporary_fleets = {}

        self._issued_orders = {}
        self._distance_cache = {}

    def num_planets(self):
        return len(self._planets)

    def get_planet(self, planet_id):
        return self._planets[planet_id]

    def num_fleets(self):
        return len(self._fleets)

    def get_fleet(self, fleet_id):
        return self._fleets[fleet_id]

    def planets(self):
        return self._planets

    def my_planets(self):
        return list(filter(lambda p: p.owner() == 1, self._planets))

    def neutral_planets(self):
        return list(filter(lambda p: p.owner() == 0, self._planets))

    def enemy_planets(self):
        return list(filter(lambda p: p.owner() == 2, self._planets))

    def not_my_planets(self):
        return list(filter(lambda p: p.owner() != 1, self._planets))

    def fleets(self):
        return self._fleets

    def my_fleets(self):
        return list(filter(lambda f: f.owner() == 1, self._fleets))

    def enemy_fleets(self):
        return list(filter(lambda f: f.owner() == 2, self._fleets))

    def to_string(self):
        s = ""
        for p in self._planets:
            s += "P {} {} {} {} {}\n".format(p.x(), p.y(), p.owner(), p.num_ships(), p.growth_rate())
        for f in self._fleets:
            s += "F {} {} {} {} {} {}\n".format(f.owner(), f.num_ships(), f.source_planet(), f.destination_planet(),
                                                f.total_trip_length(), f.turns_remaining())
        return s

    def distance(self, source_planet, destination_planet, raw=False):
        try:
            return self._distance_cache[tuple(sorted((source_planet, destination_planet)))][raw]
        except KeyError:
            source = self._planets[source_planet]
            destination = self._planets[destination_planet]
            raw_distance = utils.distance(source.x(), source.y(), destination.x(), destination.y())
            distance = int(math.ceil(raw_distance))

            self._distance_cache[tuple(sorted((source_planet, destination_planet)))] = (distance, raw_distance)
            return raw_distance if raw else distance

    def issue_order(self, source_planet, destination_planet, num_ships):
        if num_ships == 0 or source_planet == destination_planet:
            return

        key = (source_planet, destination_planet)

        try:
            self._issued_orders[key] += num_ships
        except KeyError:
            self._issued_orders[key] = num_ships

    def is_alive(self, player_id):
        return any(map(lambda p: p.owner() == player_id, self._planets)) or \
               any(map(lambda f: f.owner() == player_id, self._fleets))

    def parse_game_state(self, s):
        lines = s.split("\n")

        for line in lines:
            line = line.split("#")[0]  # remove comments
            tokens = line.split(" ")
            if len(tokens) == 1:
                continue
            if tokens[0] == "P":
                if len(tokens) != 6:
                    return False
                p = Planet(self._planet_id_counter,  # The ID of this planet
                           int(tokens[3]),  # owner
                           int(tokens[4]),  # num_ships
                           int(tokens[5]),  # growth_rate
                           float(tokens[1]),  # x
                           float(tokens[2]))  # y
                self._planet_id_counter += 1
                self._planets.append(p)
            elif tokens[0] == "F":
                if len(tokens) != 7 or int(tokens[2]) == 0:
                    return False
                key = (int(tokens[1]), int(tokens[4]), int(tokens[6]))
                try:
                    self._temporary_fleets[key][0] += int(tokens[2])
                except KeyError:
                    self._temporary_fleets[key] = [int(tokens[2]), int(tokens[3]), int(tokens[5])]
            else:
                return False
        return True

    def _get_future_neutrals(self):
        future_planets = [{}, {}]
        pseudo_ships = {p.planet_id(): p.num_ships() for p in self.neutral_planets()}
        neutral_arriving_fleets = filter(lambda f: f.destination_planet() in pseudo_ships, self.fleets())
        neutral_arriving_fleets = sorted(neutral_arriving_fleets, key=lambda f: f.destination_planet())
        neutral_arriving_fleets = sorted(neutral_arriving_fleets, key=lambda f: f.turns_remaining())
        for index, fleet in enumerate(neutral_arriving_fleets):
            try:
                pseudo_ships[fleet.destination_planet()] -= fleet.num_ships()
                if pseudo_ships[fleet.destination_planet()] < 0:
                    next_fleet = neutral_arriving_fleets[index + 1]
                    if fleet.destination_planet() != next_fleet.destination_planet() or \
                            next_fleet.turns_remaining() > fleet.turns_remaining():
                        destination_planet = self.get_planet(fleet.destination_planet())
                        future_planets[fleet.owner() - 1][destination_planet] = (
                            fleet.turns_remaining(), abs(pseudo_ships[fleet.destination_planet()]))
                        del pseudo_ships[fleet.destination_planet()]
                    elif fleet.destination_planet() == next_fleet.destination_planet():
                        destination_planet = self.get_planet(fleet.destination_planet())
                        if fleet.num_ships() > next_fleet.num_ships():
                            future_planets[fleet.owner() - 1][destination_planet] = (
                                fleet.turns_remaining(), fleet.num_ships() - next_fleet.num_ships())
                            del pseudo_ships[fleet.destination_planet()]
                        elif fleet.num_ships() < next_fleet.num_ships():
                            future_planets[next_fleet.owner() - 1][destination_planet] = (
                                next_fleet.turns_remaining(), next_fleet.num_ships() - fleet.num_ships())
                            del pseudo_ships[fleet.destination_planet()]
                        else:
                            pseudo_ships[fleet.destination_planet()] = 0
                elif fleet.destination_planet() == neutral_arriving_fleets[index + 1].destination_planet():
                    pseudo_ships[fleet.destination_planet()] += min(fleet.num_ships(),
                                                                    neutral_arriving_fleets[index + 1].num_ships())
            except IndexError:
                destination_planet = self.get_planet(fleet.destination_planet())
                future_planets[fleet.owner() - 1][destination_planet] = (
                    fleet.turns_remaining(), abs(pseudo_ships[fleet.destination_planet()]))
                del pseudo_ships[fleet.destination_planet()]
            except KeyError:
                pass

        self.my_future_neutrals = future_planets[0]
        self.enemy_future_neutrals = future_planets[1]

    def _get_maximum_ships(self):
        for planet in self.planets():
            my_arriving_ships = [0 for _ in range(2 * self.map_size)]
            for my_planet in self.my_planets():
                distance = max(0, self.distance(my_planet.planet_id(), planet.planet_id()) - 1)
                my_arriving_ships[distance] += my_planet.num_ships()
                for turn in range(distance, len(my_arriving_ships)):
                    my_arriving_ships[turn] += my_planet.growth_rate()
            for my_fleet in self.my_fleets():
                destination_planet = self.get_planet(my_fleet.destination_planet())
                if destination_planet.owner() == 1 or \
                        (destination_planet in self.my_future_neutrals and
                         self.my_future_neutrals[destination_planet][0] < my_fleet.turns_remaining()):
                    distance = my_fleet.turns_remaining() + \
                        self.distance(my_fleet.destination_planet(), planet.planet_id()) - 1
                    my_arriving_ships[distance] += my_fleet.num_ships()
            for my_planet, (turns_to_take, excess_ships) in self.my_future_neutrals.items():
                distance = turns_to_take + self.distance(my_planet.planet_id(), planet.planet_id()) - 1
                my_arriving_ships[distance] += excess_ships
                for turn in range(distance + 1, len(my_arriving_ships)):
                    my_arriving_ships[turn] += my_planet.growth_rate()
            planet.my_maximum_ships = my_arriving_ships

            enemy_arriving_ships = [0 for _ in range(2 * self.map_size)]
            for enemy_planet in self.enemy_planets():
                distance = max(0, self.distance(enemy_planet.planet_id(), planet.planet_id()) - 1)
                enemy_arriving_ships[distance] += enemy_planet.num_ships()
                for turn in range(distance, len(enemy_arriving_ships)):
                    enemy_arriving_ships[turn] += enemy_planet.growth_rate()
            for enemy_fleet in self.enemy_fleets():
                destination_planet = self.get_planet(enemy_fleet.destination_planet())
                if destination_planet.owner() == 2 or \
                        (destination_planet in self.enemy_future_neutrals and
                         self.enemy_future_neutrals[destination_planet][0] < enemy_fleet.turns_remaining()):
                    distance = enemy_fleet.turns_remaining() + \
                        self.distance(enemy_fleet.destination_planet(), planet.planet_id()) - 1
                    enemy_arriving_ships[distance] += enemy_fleet.num_ships()
            for enemy_planet, (turns_to_take, excess_ships) in self.enemy_future_neutrals.items():
                distance = turns_to_take + self.distance(enemy_planet.planet_id(), planet.planet_id()) - 1
                enemy_arriving_ships[distance] += excess_ships
                for turn in range(distance + 1, len(enemy_arriving_ships)):
                    enemy_arriving_ships[turn] += enemy_planet.growth_rate()
            planet.enemy_maximum_ships = enemy_arriving_ships

    def _get_info(self):
        self.turns_remaining = (TOTAL_TURNS - PlanetWars.turn)
        self.map_size = 2 * math.ceil(utils.distance(0, 0, self._planets[0].x(), self._planets[0].y()))
        self.my_total_ships = sum(map(lambda x: x.num_ships(), self.my_planets() + self.my_fleets()))
        self.enemy_total_ships = sum(map(lambda x: x.num_ships(), self.enemy_planets() + self.enemy_fleets()))
        self.my_growth_rate = sum(map(lambda p: p.growth_rate(), self.my_planets()))
        self.enemy_growth_rate = sum(map(lambda p: p.growth_rate(), self.enemy_planets()))
        self.total_growth = sum(map(lambda p: p.growth_rate(), self.planets()))

        self._get_future_neutrals()
        self._get_maximum_ships()

        my_final_ships = self.my_total_ships + self.turns_remaining * self.my_growth_rate + \
            sum(e + (self.turns_remaining - t) * p.growth_rate() - p.num_ships()
                for p, (t, e) in self.my_future_neutrals.items())
        enemy_final_ships = self.enemy_total_ships + self.turns_remaining * self.enemy_growth_rate + \
            sum(e + (self.turns_remaining - t) * p.growth_rate() - p.num_ships()
                for p, (t, e) in self.enemy_future_neutrals.items())
        self.time_result = my_final_ships - enemy_final_ships

        for fleet in self.fleets():
            if self.get_planet(fleet.destination_planet()).owner() not in (0, fleet.owner()):
                self.peaceful = False
                break
        else:
            self.peaceful = True

        for fleet in self.fleets():
            if fleet.owner() != self.get_planet(fleet.destination_planet()).owner():
                self.chilling = False
                break
        else:
            self.chilling = True

    def initialise(self):
        for (owner, destination, turns_remaining), (num_ships, source, trip_length) in self._temporary_fleets.items():
            f = Fleet(int(owner),  # owner
                      int(num_ships),  # num_ships
                      int(source),  # source
                      int(destination),  # destination
                      int(trip_length),  # total_trip_length
                      int(turns_remaining))  # turns_remaining
            self._fleets.append(f)

        self._get_info()

    def finish_turn(self):
        PlanetWars.turn += 1

        for (source_planet, destination_planet), num_ships in self._issued_orders.items():
            sys.stdout.write("{} {} {}\n".format(source_planet, destination_planet, num_ships))

        sys.stdout.write("go\n")
        sys.stdout.flush()

