# class StatefulTimer:
#     """Manage state for actions, implementing a lock mechanism with a delay-based unlock."""

#     def __init__(self):
#         self.last_access = datetime.now()
#         self.locked = False
#         self.last_alert_time = None
#         self.cooldown_period = timedelta(seconds=config["SECS_LAST_MOVEMENT"])  # Cooldown duration


#     def unlock(self):
#         self.locked = False
#         logger.info("Timer unlocked")

#     def check(self):
#         now = datetime.now()

#         if self.last_alert_time and now < self.last_alert_time + self.cooldown_period:
#             return False

#         if not self.locked and self.last_access + timedelta(seconds=config["SECS_LAST_MOVEMENT"]) < now:
#             self.locked = True
#             asyncio.create_task(self._delayed_unlock())
#             return True
#         return False

#     async def _delayed_unlock(self):
#         await asyncio.sleep(config["SECS_UNLOCK_AFTER_ALERT"])
#         self.unloc