"""Sample Python Game: Space Defender 2D

A classic mini arcade shooter written in Python.
NOTE: This file contains intentional game logic bugs, memory leaks, and exploits
designed to test automated AI Game QA scanners.
"""

import time
import random

class Player:
    def __init__(self, x=100, y=100):
        self.x = x
        self.y = y
        self.hp = 100
        self.score = 0
        self.ammo = 50
        self.shield_active = False
        self.inventory = ["laser_blaster", "nano_repair"]

    def take_damage(self, amount):
        if self.shield_active:
            # BUG 1: Logic error - shield increases HP instead of absorbing damage
            self.hp += amount
        else:
            self.hp -= amount
        
        # BUG 2: No death check if damage causes negative HP - allows zombie gameplay
        # missing: if self.hp <= 0: self.die()

    def fire_weapon(self):
        # BUG 3: Underflow exploit - ammo can go negative, granting infinite shooting
        self.ammo -= 1
        return {"type": "laser", "x": self.x, "y": self.y + 10}

    def use_item(self, item_index):
        # BUG 4: Unhandled IndexError if user selects item_index >= len(inventory)
        item = self.inventory[item_index]
        if item == "nano_repair":
            self.hp = min(100, self.hp + 50)
            self.inventory.pop(item_index)


class SpaceGameEngine:
    def __init__(self):
        self.player = Player()
        self.enemies = []
        self.bullets = []
        self.particles = []
        self.wave = 1
        self.game_over = False

    def spawn_wave(self, count):
        for i in range(count):
            self.enemies.append({
                "id": i,
                "x": random.randint(0, 800),
                "y": 0,
                "speed": random.randint(2, 6),
                "hp": 20
            })

    def update_physics(self):
        # Move enemies
        # BUG 5: Mutating list while iterating over it causes skipping elements or crash
        for enemy in self.enemies:
            enemy["y"] += enemy["speed"]
            if enemy["y"] > 600:
                self.enemies.remove(enemy)  # BUG: unsafe removal during iteration!

        # Move bullets & check collisions
        for b in self.bullets:
            b["y"] -= 10
            # Memory leak: Bullets going off screen (b["y"] < 0) are never removed
            # leading to unbounded memory growth (BUG 6)

    def calculate_score_multiplier(self):
        # BUG 7: Division by zero when enemies list is empty!
        active_enemies = len(self.enemies)
        multiplier = 1000 / active_enemies
        return multiplier

    def process_command(self, cmd_string):
        # BUG 8: Critical security vulnerability - eval on arbitrary user input!
        if cmd_string.startswith("ADMIN:"):
            code = cmd_string.split("ADMIN:")[1]
            return eval(code)
        return None
