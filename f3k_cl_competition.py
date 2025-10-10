import logging

from task_data import f3k_task_timing_data

SHORT_TIME_DEBUG = False

class Section:
    """
    Represents a section with the running of a group - prep time, test time, no-fly, working, landing etc
    """
    def __init__(self, seconds_length, group_obj, round_obj, section_index, event_config=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.event_config = event_config or {}
        self.round = round_obj
        self.group = group_obj
        self.updatedWeb = False # only used in announce
        self.betweenWorkingTimes = False
        self.section_index = section_index
        self.sectionTime = seconds_length
        # List of times that will trigger audio calls
        # Default is every 30 seconds + 20 down to 5.
        # Excluding the first second which will usually be covered by the pre-section
        # announcement or the start of section announcement
        self.say_seconds = list((x for x in range(seconds_length-1, 0 ,-1) if x%30==0)) + list(range(20,4,-1))
        # Dict of timestamps for audio callouts
        # All these must be integer second values


    def __repr__(self):
        return f"Section {self.get_description()} of Group:{self.group.group_number} of Round:{self.round.round_number} {int(self.sectionTime):3d}secs"
    ## If there are multiple instances of a section class
    ## in a group then lets provide the index - e.g. all up, no-fly, work, landing all can have an index
    def get_flight_number(self):
        try: 
            return list((x for x in self.group.sections if isinstance(x, self.__class__))).index(self) + 1
        except ValueError:
            return 1
    def get_next_section(self):
        try: return self.group.sections[self.section_index+1]
        except IndexError: 
            self.logger.debug(f"Failed to get_next_section. {self.group.sections}, index: {self.section_index+1}")
            return None
    def get_previous_section(self):
        try: return self.group.sections[self.section_index-1]
        except IndexError: return None

    def is_no_fly(self):
        # Make the default restrictive so we don't use the base class!
        return True
    def get_serial_code(self):
        return "ST"
    def get_description(self):
        return "Base class, shouldn't see this one."  

class PrepSection(Section):
    def is_no_fly(self):
        # Note which way round the booleans are here!
        # Config is "be strict", so True means no-fly here
        # This method is "is this a no fly section?"
        return self.event_config.get('use_strict_test_time', False)
    def get_serial_code(self):
        return "PT"
    def get_description(self):
        return "Preparation Time"
        

    def announcement(self):
        return self.group.announce_sound
        
class TestSection(Section):
    def is_no_fly(self):
        return False
    def get_serial_code(self):
        return "TT"
    def get_description(self):
        return "Test Flying Time"  

class NoFlySection(Section):
    def is_no_fly(self):
        return True
    def get_serial_code(self):
        return "NF"
    def get_description(self):
        return "No Fly Time"    


class AllUpNoFlySection(NoFlySection):
    ## Used between the working times
    def get_flight_number(self):
        try: 
            return list((x for x in self.group.sections if (isinstance(x, AllUpNoFlySection) or isinstance(x, NoFlySection)))).index(self) + 1
        except ValueError:
            return 1
class WorkingSection(Section):
    def is_no_fly(self):
        return False
    def get_serial_code(self):
        return "WT"
    def get_description(self):
        return "Working Time"    

class LandingSection(Section):
    def is_no_fly(self):
        return True # kind of
    def get_serial_code(self):
        return "LT"
    def get_description(self):
        return "Landing Window"    
        

class GapSection(Section):
    def get_description(self):
        return "Waiting for next group"

class AnnounceSection(Section):
    def get_description(self):
        return "Announcement in progress"
        
class ShowTimeSection(GapSection):
    def get_serial_code(self):
        return "DT"
    def get_description(self):
        return "Actual Time HH:MM"


class Group:
    """
    Represents a group within a round. Can generate its timing sections (prep, no-fly, work, land, gap).
    """
    def __init__(self, group_number, group_letter, round_obj, pilot_list, event_config=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.group_number = group_number
        self.group_letter = group_letter
        self.round = round_obj  # Reference to parent Round
        self.pilots = pilot_list  # List of pilot IDs in this group
        self.logger.debug(f"Group got config {event_config}")
        self.event_config = event_config or {}
        # Example: self.sections = list(self.sections_iter())
        
        self.sections = []
        self.populate_sections()
        self.announce_sound = None
        self.announce_sound_generating = False

    def __iter__(self):
        return (section for section in self.sections)
    
    def populate_sections(self):
        prep_time = self.event_config.get('prep_time', 300)
        test_time = self.event_config.get('test_time', 0)
        no_fly_time = self.event_config.get('no_fly_time', 60)
        work_time = getattr(self.round, 'windowTime', 600)
        land_time = self.event_config.get('land_time', 30)
        group_separation_time = self.event_config.get('group_separation_time', 120)

        ## Passing len(self.sections) so that the section knows its own index and we
        ## can use it to reference forward and back.
        self.sections.append(AnnounceSection(999, self, self.round, len(self.sections), self.event_config))
        if prep_time > 0:
            self.sections.append(PrepSection(prep_time, self, self.round, len(self.sections), self.event_config))
        if test_time > 0:
            self.sections.append(TestSection(test_time, self, self.round, len(self.sections), self.event_config))
        if no_fly_time > 0:
            self.sections.append(NoFlySection(no_fly_time, self, self.round, len(self.sections), self.event_config))
        if work_time > 0:
            self.sections.append(WorkingSection(work_time, self, self.round, len(self.sections), self.event_config))
        if land_time > 0:
            self.sections.append(LandingSection(land_time, self, self.round, len(self.sections), self.event_config))
        if group_separation_time > 0:
            self.sections.append(GapSection(group_separation_time, self, self.round, len(self.sections), self.event_config))
        self.logger.debug(f"{self.sections}")
    def __repr__(self):
        return f"Group {self.group_letter} of Round {self.round.round_number:2d}"

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

    def populate_sections(self):
        prep_time = self.event_config.get('prep_time', 300)
        test_time = self.event_config.get('test_time', 0)
        no_fly_time = self.event_config.get('no_fly_time', 60)
        work_time = getattr(self.round, 'windowTime', 600)
        land_time = self.event_config.get('land_time', 30)
        group_separation_time = self.event_config.get('group_separation_time', 120)

        self.sections.append(AnnounceSection(999, self, self.round, len(self.sections), self.event_config))
        if prep_time > 0:
            self.sections.append(PrepSection(prep_time, self, self.round, len(self.sections), self.event_config))
        if test_time > 0:
            self.sections.append(TestSection(test_time, self, self.round, len(self.sections), self.event_config))
        for i in range(self.all_up_flight_count):
            if no_fly_time > 0:
                if i == 0:
                    self.sections.append(NoFlySection(no_fly_time, self, self.round, len(self.sections), self.event_config))
                else:
                    self.sections.append(AllUpNoFlySection(no_fly_time, self, self.round, len(self.sections), self.event_config))
            if work_time > 0:
                self.sections.append(WorkingSection(work_time, self, self.round, len(self.sections), self.event_config))
            if land_time > 0:
                self.sections.append(LandingSection(land_time, self, self.round, len(self.sections), self.event_config))
        if group_separation_time > 0:
            self.sections.append(GapSection(group_separation_time, self, self.round, len(self.sections), self.event_config))

# Example usage:
# round_obj = Round('f3k_a', 'A', 1)
# group = Group(1, round_obj, event_config={'prep_time': 60, 'no_fly_time': 30})
# for section, duration in group:
#     print(section, duration)

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
    def __iter__(self):
        groups = {}
        letters= "-ABCDEFGHIJKLMNOPQRSTUVWXYZ" # Adding '-' so index matches group number
        #print (self.round_number)
        for pilot in self.standings_data:
            pilot_id = pilot['pilot_id']
            
            # prelim_standings.standings[pilot.rounds[round.flights[flight_group]]]
            if len(pilot['rounds']) >= 0:
                # Only look at this round
                try: round_data = pilot['rounds'][self.round_number - 1]
                except IndexError:
                    self.logger.warning(f"Pilot {pilot_id} has no data for round {self.round_number}")
                    continue
                assert round_data['round_number'] == self.round_number
                for flight in round_data['flights']:
                    if flight['flight_group'] not in groups:
                        groups[flight['flight_group']] = []
                    groups[flight['flight_group']].append(pilot_id)
        for group_letter in sorted(groups): 
            group_number = letters.index(group_letter)
            # Make All Up group if this is an All Up round
            if self.short_code.startswith("f3k_c"):
                yield AllUpGroup(group_number, group_letter, self, groups[group_letter], self.event_config) 
            else:
                yield Group(group_number, group_letter, self, groups[group_letter], self.event_config)

    #def __iter__(self):
    #    return (group for group in self.groups)

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
    ###draw[pilot.pilot_id][task.round_number] = pilot.rounds[parseInt(task.round_number) - 1].flights[0].flight_group
  return round_data   

