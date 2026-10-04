"""
SHADOW DESCENT: A Terminal Roguelike
Run directly with: python shadow_descent.py
Controls: W/A/S/D to move/attack, I for inventory, H for help, Q to quit.
"""

import os
import sys
import random
import copy
from typing import List, Tuple, Dict, Optional

# --- CONFIGURATION & CONSTANTS ---
MAP_WIDTH = 45
MAP_HEIGHT = 20
MAX_ROOMS = 7
ROOM_MIN_SIZE = 4
ROOM_MAX_SIZE = 9
MAX_ENEMIES_PER_ROOM = 2

TILE_WALL = '#'
TILE_FLOOR = '.'
TILE_PLAYER = '@'
TILE_STAIRS = '>'

# --- ENTITY DEFINITIONS ---
class Item:
    def __init__(self, name: str, item_type: str, value: int):
        self.name = name
        self.item_type = item_type  # 'heal', 'attack', 'defense'
        self.value = value

    def __repr__(self):
        return f"{self.name} (+{self.value} {self.item_type})"

class Entity:
    def __init__(self, x: int, y: int, name: str, char: str, hp: int, attack: int, defense: int):
        self.x = x
        self.y = y
        self.name = name
        self.char = char
        self.max_hp = hp
        self.hp = hp
        self.base_attack = attack
        self.base_defense = defense

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, dmg: int) -> int:
        actual_damage = max(1, dmg - self.base_defense)
        self.hp -= actual_damage
        return actual_damage

class Player(Entity):
    # BUG CANDIDATE 1: Default argument evaluation
    def __init__(self, x: int, y: int, inventory: List[Item] = []):
        super().__init__(x, y, "Adventurer", TILE_PLAYER, hp=35, attack=8, defense=2)
        self.inventory = inventory
        self.gold = 0
        self.level = 1
        self.xp = 0

    @property
    def total_attack(self) -> int:
        bonus = sum(item.value for item in self.inventory if item.item_type == 'attack')
        return self.base_attack + bonus

    @property
    def total_defense(self) -> int:
        bonus = sum(item.value for item in self.inventory if item.item_type == 'defense')
        return self.base_defense + bonus

# --- DUNGEON GENERATION ---
class Rect:
    def __init__(self, x: int, y: int, w: int, h: int):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    @property
    def center(self) -> Tuple[int, int]:
        center_x = (self.x1 + self.x2) // 2
        center_y = (self.y1 + self.y2) // 2
        return center_x, center_y

    def intersects(self, other: 'Rect') -> bool:
        # BUG CANDIDATE 2: Boundary overlap condition
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 < other.y2 and self.y2 > other.y1)

class Dungeon:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # BUG CANDIDATE 3: 2D Grid initialization & reference aliasing
        self.grid = [[TILE_WALL] * width for _ in range(height)]
        self.rooms: List[Rect] = []
        self.enemies: List[Entity] = []
        self.items: Dict[Tuple[int, int], Item] = {}
        self.stairs_pos: Tuple[int, int] = (0, 0)

    def create_room(self, room: Rect):
        for x in range(room.x1 + 1, room.x2):
            for y in range(room.y1 + 1, room.y2):
                self.grid[y][x] = TILE_FLOOR

    def create_h_tunnel(self, x1: int, x2: int, y: int):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.grid[y][x] = TILE_FLOOR

    def create_v_tunnel(self, y1: int, y2: int, x: int):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.grid[y][x] = TILE_FLOOR

    def generate(self, floor_level: int) -> Tuple[int, int]:
        self.rooms.clear()
        self.enemies.clear()
        self.items.clear()
        self.grid = [[TILE_WALL] * self.width for _ in range(self.height)]

        player_start = (self.width // 2, self.height // 2)

        for _ in range(MAX_ROOMS):
            w = random.randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
            h = random.randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
            x = random.randint(1, self.width - w - 2)
            y = random.randint(1, self.height - h - 2)
            new_room = Rect(x, y, w, h)

            failed = False
            for other_room in self.rooms:
                if new_room.intersects(other_room):
                    failed = True
                    break

            if not failed:
                self.create_room(new_room)
                (new_x, new_y) = new_room.center

                if len(self.rooms) == 0:
                    player_start = (new_x, new_y)
                else:
                    (prev_x, prev_y) = self.rooms[-1].center
                    if random.choice([True, False]):
                        self.create_h_tunnel(prev_x, new_x, prev_y)
                        self.create_v_tunnel(prev_y, new_y, new_x)
                    else:
                        self.create_v_tunnel(prev_y, new_y, prev_x)
                        self.create_h_tunnel(prev_x, new_x, new_y)

                self._spawn_room_contents(new_room, floor_level)
                self.rooms.append(new_room)

        # Place exit stairs in last room
        if self.rooms:
            self.stairs_pos = self.rooms[-1].center

        return player_start

    def _spawn_room_contents(self, room: Rect, floor_lvl: int):
        num_enemies = random.randint(0, MAX_ENEMIES_PER_ROOM)
        for _ in range(num_enemies):
            ex = random.randint(room.x1 + 1, room.x2 - 1)
            ey = random.randint(room.y1 + 1, room.y2 - 1)
            if random.random() < 0.6:
                enemy = Entity(ex, ey, "Goblin", 'g', hp=10 + floor_lvl * 2, attack=4 + floor_lvl, defense=1)
            else:
                enemy = Entity(ex, ey, "Orc", 'o', hp=16 + floor_lvl * 3, attack=7 + floor_lvl, defense=2)
            self.enemies.append(enemy)

        if random.random() < 0.4:
            ix = random.randint(room.x1 + 1, room.x2 - 1)
            iy = random.randint(room.y1 + 1, room.y2 - 1)
            item_pool = [
                Item("Minor Health Potion", "heal", 12),
                Item("Iron Dagger", "attack", 3),
                Item("Buckler Shield", "defense", 2)
            ]
            self.items[(ix, iy)] = random.choice(item_pool)

    def is_blocked(self, x: int, y: int) -> bool:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return True
        return self.grid[y][x] == TILE_WALL

    def get_enemy_at(self, x: int, y: int) -> Optional[Entity]:
        for e in self.enemies:
            if e.x == x and e.y == y and e.is_alive:
                return e
        return None

# --- ENGINE ---
class GameEngine:
    def __init__(self):
        self.floor = 1
        self.dungeon = Dungeon(MAP_WIDTH, MAP_HEIGHT)
        self.player = Player(0, 0)
        self.messages: List[str] = ["Welcome to Shadow Descent! Defeat monsters and descend."]
        self.setup_floor()

    def log(self, text: str):
        self.messages.append(text)
        if len(self.messages) > 4:
            self.messages.pop(0)

    def setup_floor(self):
        px, py = self.dungeon.generate(self.floor)
        self.player.x = px
        self.player.y = py
        self.log(f"Entered Dungeon Floor {self.floor}.")

    def render(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        view = [row[:] for row in self.dungeon.grid]

        sx, sy = self.dungeon.stairs_pos
        view[sy][sx] = TILE_STAIRS

        for (ix, iy), item in self.dungeon.items.items():
            view[iy][ix] = '!'

        for enemy in self.dungeon.enemies:
            if enemy.is_alive:
                view[enemy.y][enemy.x] = enemy.char

        view[self.player.y][self.player.x] = self.player.char

        print(f"=== SHADOW DESCENT | Floor {self.floor} ===")
        print(f"HP: {self.player.hp}/{self.player.max_hp} | ATK: {self.player.total_attack} | DEF: {self.player.total_defense} | XP: {self.player.xp}")
        print("-" * MAP_WIDTH)

        for row in view:
            print("".join(row))

        print("-" * MAP_WIDTH)
        for msg in self.messages:
            print(f"> {msg}")
        print("-" * MAP_WIDTH)

    def handle_player_move(self, dx: int, dy: int):
        nx, ny = self.player.x + dx, self.player.y + dy

        target = self.dungeon.get_enemy_at(nx, ny)
        if target:
            # Player attacks enemy
            damage = target.take_damage(self.player.total_attack)
            self.log(f"You struck {target.name} for {damage} dmg!")
            if not target.is_alive:
                self.log(f"Defeated {target.name}!")
                # BUG CANDIDATE 4: Exp gain calculation integer division bug
                xp_gain = int(target.max_hp * (10 / 8))  # subtle rounding issue vs scaled floor calculation
                self.player.xp += xp_gain
            return

        if not self.dungeon.is_blocked(nx, ny):
            self.player.x = nx
            self.player.y = ny

            # Check item pickup
            pos = (nx, ny)
            if pos in self.dungeon.items:
                picked = self.dungeon.items.pop(pos)
                if picked.item_type == 'heal':
                    self.player.hp = min(self.player.max_hp, self.player.hp + picked.value)
                    self.log(f"Drank {picked.name}. Restored {picked.value} HP.")
                else:
                    self.player.inventory.append(picked)
                    self.log(f"Equipped {picked.name}!")

            # Check stairs
            if (nx, ny) == self.dungeon.stairs_pos:
                self.floor += 1
                self.setup_floor()

    def update_enemies(self):
        # BUG CANDIDATE 5: Mutating collection during iteration / simultaneous removal
        for enemy in self.dungeon.enemies:
            if not enemy.is_alive:
                self.dungeon.enemies.remove(enemy)
                continue

            # Basic tracking AI
            dx = 1 if self.player.x > enemy.x else -1 if self.player.x < enemy.x else 0
            dy = 1 if self.player.y > enemy.y else -1 if self.player.y < enemy.y else 0

            # Distance check
            dist = abs(self.player.x - enemy.x) + abs(self.player.y - enemy.y)
            if dist == 1:
                # Attack player
                dmg = max(1, enemy.base_attack - self.player.total_defense)
                self.player.hp -= dmg
                self.log(f"{enemy.name} hit you for {dmg} dmg!")
            elif dist < 6:
                # Move closer if unobstructed
                tx, ty = enemy.x + dx, enemy.y + dy
                if not self.dungeon.is_blocked(tx, ty) and not self.dungeon.get_enemy_at(tx, ty):
                    enemy.x = tx
                    enemy.y = ty

    def run(self):
        action_map = {
            'w': (0, -1),
            's': (0, 1),
            'a': (-1, 0),
            'd': (1, 0),
            'q': None
        }

        while self.player.is_alive:
            self.render()
            try:
                cmd = input("Action [WASD, I: Inv, Q: Quit]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                break

            if cmd == 'q':
                print("Fled the dungeon...")
                break
            elif cmd == 'i':
                self.log("Inventory: " + (", ".join(i.name for i in self.player.inventory) or "Empty"))
                continue
            elif cmd in action_map:
                dx, dy = action_map[cmd]
                self.handle_player_move(dx, dy)
                self.update_enemies()
            else:
                self.log("Invalid key. Use W/A/S/D.")

        if not self.player.is_alive:
            self.render()
            print("YOU DIED. Game Over.")

if __name__ == "__main__":
    game = GameEngine()
    game.run()