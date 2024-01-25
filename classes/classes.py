"""
The IdleRPG Discord Bot
Copyright (C) 2018-2021 Diniboy and Gelbpunkt

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
from __future__ import annotations

from enum import Enum


class GameClass(Enum):
    def class_name(self) -> str:
        out = []
        for char in self.name:
            if char.isupper():
                out.append(char)
            else:
                out[-1] += char
        return " ".join(out)

    def get_class_line(self) -> type[GameClass]:
        return self.__class__

    def get_class_line_name(self) -> str:
        return self.__class__.__name__

    def in_class_line(self, class_line: type[GameClass]) -> bool:
        return class_line == self.__class__

    def class_grade(self) -> int:
        return self.value + 1


class Warrior(GameClass):
    Grunt = 0
    Mercenary = 1
    Berserker = 2
    Vanguard = 3
    Warlord = 4
    Champion = 5
    BattleMaster = 6


class SantasHelper(GameClass):
    LittleHelper = 0
    GiftGatherer = 1
    HolidayAide = 2
    JoyfulJester = 3
    YuletideGuardian = 4
    FestiveEnforcer = 5
    FestiveChampion = 6


class Thief(GameClass):
    Mugger = 0
    Thief = 1
    Rogue = 2
    Bandit = 3
    Chunin = 4
    Renegade = 5
    Assassin = 6



class Mage(GameClass):
    Juggler = 0
    Witcher = 1
    Enchanter = 2
    Mage = 3
    Warlock = 4
    DarkCaster = 5
    WhiteSorcerer = 6


class Paragon(GameClass):
    Novice = 0
    Proficient = 1
    Artisan = 2
    Master = 3
    Champion = 4
    Vindicator = 5
    Paragon = 6


class Paladin(GameClass):
    Squire = 0
    FootKnight = 1
    Crusader = 2
    Templar = 3
    Justicar = 4
    DivineChampion = 5
    Archpaladin = 6


class Ranger(GameClass):
    Caretaker = 0
    Tamer = 1
    Trainer = 2
    Bowman = 3
    Hunter = 4
    Warden = 5
    Ranger = 6


class Raider(GameClass):
    Adventurer = 0
    Swordsman = 1
    Fighter = 2
    Swashbuckler = 3
    Dragonslayer = 4
    Raider = 5
    EternalHero = 6


class Ritualist(GameClass):
    Priest = 0
    Mysticist = 1
    Doomsayer = 2
    Seer = 3
    Oracle = 4
    Prophet = 5
    Ritualist = 6


class Reaper(GameClass):
    Deathshroud = 0
    SoulWarden = 1
    Reaper = 2
    PhantomScythe = 3
    SoulSnatcher = 4
    Deathbringer = 5
    GrimReaper = 6


def get_class_evolves(class_: type[GameClass]) -> list[GameClass]:
    return list(class_.__members__.values())


ALL_CLASSES = {
    class_.class_name(): class_
    for class_ in list(Warrior.__members__.values())
                  + list(Thief.__members__.values())
                  + list(Mage.__members__.values())
                  + list(Paragon.__members__.values())
                  + list(Raider.__members__.values())
                  + list(Ranger.__members__.values())
                  + list(Ritualist.__members__.values())
                  + list(Paladin.__members__.values())
                  + list(Reaper.__members__.values())
                  + list(SantasHelper.__members__.values())
}

ALL_CLASSES_TYPES = {
    "Thief": Thief,
    "Mage": Mage,
    "Paragon": Paragon,
    "Raider": Raider,
    "Ranger": Ranger,
    "Ritualist": Ritualist,
    "Warrior": Warrior,
    "Paladin": Paladin,
    "Reaper": Reaper,
    "SantasHelper": SantasHelper,
}


def from_string(class_: str) -> GameClass | None:
    return ALL_CLASSES.get(class_, None)


def get_name(class_: type[GameClass]) -> str:
    return class_.__name__


def get_first_evolution(class_: type[GameClass]) -> GameClass:
    return list(class_.__members__.values())[0]
