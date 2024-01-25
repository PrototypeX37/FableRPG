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
from enum import Enum


class OrderedEnum(Enum):
    # The default is Any, that breaks the comparisons
    value: int

    def __ge__(self, other: "OrderedEnum") -> bool:
        if self.__class__ is other.__class__:
            return self.value >= other.value
        raise NotImplementedError()

    def __gt__(self, other: "OrderedEnum") -> bool:
        if self.__class__ is other.__class__:
            return self.value > other.value
        raise NotImplementedError()

    def __le__(self, other: "OrderedEnum") -> bool:
        if self.__class__ is other.__class__:
            return self.value <= other.value
        raise NotImplementedError()

    def __lt__(self, other: "OrderedEnum") -> bool:
        if self.__class__ is other.__class__:
            return self.value < other.value
        raise NotImplementedError()


class DonatorRank(OrderedEnum):
    basic = 1
    bronze = 2
    silver = 3
    gold = 4
    emerald = 5
    ruby = 6
    diamond = 7
