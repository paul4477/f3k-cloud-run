import logging

from task_data import f3k_task_timing_data

class Group:
    """
    Represents a group within a round.
    """
    def __init__(self, group_number, group_letter, round_obj, pilot_list, event_config=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.group_number = group_number
        self.group_letter = group_letter
        self.round = round_obj  # Reference to parent Round
        self.pilots = pilot_list  # List of pilot IDs in this group
        #self.logger.debug(f"Group got config {event_config}")
        self.event_config = event_config or {}
                
        self.sections = []
        self.announce_sound = None
        self.announce_sound_generating = False


class AllUpGroup(Group):
    def __init__(self, group_number, group_letter, round_obj, pilot_list, event_config=None):
        match round_obj.short_code:
            case "f3k_c":
                self.all_up_flight_count = 3
            case "f3k_c2":
                self.all_up_flight_count = 4
            case "f3k_c3":
                self.all_up_flight_count = 5
            case _:
                self.logger.error(f"Unexpected round short_code in All Up group: {round_obj.short_code}")
        super().__init__(group_number, group_letter, round_obj, pilot_list, event_config=None)


class Round():
    def __init__(self, short_code, short_name, round_number, event_config=None):
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.short_code = short_code
        self.round_number = round_number
        self.short_name = short_name
        self.event_config = event_config or {}
        self.task_name = f3k_task_timing_data[self.short_code]['name']
        self.task_description = f3k_task_timing_data[self.short_code]['description']
        self.windowTime = f3k_task_timing_data[self.short_code]['windowTime']
        self.groups = []

    def __repr__(self):
        return f"Round {self.round_number:2d} {self.short_name}, {int(self.windowTime/60):2d}mins"

    def set_group_data(self, prelim_standings):
        self.standings_data = prelim_standings
        self.populate_groups()
        
    def populate_groups(self):
        groups = {}
        letters= "-ABCDEFGHIJKLMNOPQRSTUVWXYZ" # Adding '-' so index matches group number

        for pilot in self.standings_data:
            pilot_id = pilot['pilot_id']
            
            # Only look at this round. The rounds are not guaranteed to be
            # ordered, so find it by its round number rather than its index.
            round_data = next(
                (
                    candidate
                    for candidate in pilot['rounds']
                    if candidate.get('round_number') == self.round_number
                ),
                None,
            )
            if round_data is None:
                self.logger.warning(f"Pilot {pilot_id} has no data for round {self.round_number}")
                continue
            for flight in round_data['flights']:
                if flight['flight_group'] not in groups:
                    groups[flight['flight_group']] = []
                groups[flight['flight_group']].append(pilot_id)
        for group_letter in sorted(groups): 
            group_number = letters.index(group_letter)
            # Make All Up group if this is an All Up round
            if self.short_code.startswith("f3k_c"):
                self.groups.append(AllUpGroup(group_number, group_letter, self, groups[group_letter], self.event_config) )
            else:
                self.groups.append(Group(group_number, group_letter, self, groups[group_letter], self.event_config))


class Pilot:
    def __init__(self, pilot_json):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.id = pilot_json['pilot_id']
        self.name = pilot_json['pilot_first_name'] + " " + pilot_json['pilot_last_name']
        self.logger.debug(f"Loading pilot {pilot_json['pilot_id']} {pilot_json['pilot_last_name']}")

    def __repr__(self):
        return f"Pilot: {self.name} ({self.id})"
    
def make_rounds(json_data, event_config=None):
  round_data = []
  event_config = event_config or {}
  
  for round in json_data['event']['tasks']:
    
    r = Round(
       round['flight_type_code'], 
       round['flight_type_name_short'], 
       round['round_number'],
       event_config=event_config
    )
    r.set_group_data(json_data['event']['prelim_standings']['standings'])
    round_data.append( r )
  return round_data   

class f3k_event:
    def __init__(self, data):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.event_id = data['event']['event_id']
        self.rounds = []
        self.pilots = {}
        self.load_data(data)

    def _set_pilots(self, raw_json):
        pilots = {}
        for pilot in raw_json['event']['pilots']:
            pilots[int(pilot['pilot_id'])] = Pilot(pilot)
        return pilots
    
    def load_data(self, raw_json):
        self.rounds = make_rounds(raw_json)
        self.pilots = self._set_pilots(raw_json)
        # Store in case we need it later
        self.raw_json = raw_json
        self.logger.info(f"Loaded event {self.event_id}: {len(self.rounds)} rounds, {len(self.pilots)} pilots")
        for r in self.rounds:
            group_summary = ", ".join(
                f"{g.group_letter}:[{', '.join(self.pilots[p].name for p in g.pilots if p in self.pilots)}]"
                for g in r.groups
            )
            self.logger.debug(f"  Round {r.round_number} ({r.short_code}): {group_summary}")
    def __json__(self):
        return self.raw_json
