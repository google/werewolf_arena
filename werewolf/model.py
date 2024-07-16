# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import enum
import json
import random
from typing import Any, Dict, List, Optional, Tuple, Union

from werewolf.lm import LmLog, generate
from werewolf.prompts import ACTION_PROMPTS_AND_SCHEMAS
from werewolf.utils import Deserializable
from werewolf.config import  MAX_DEBATE_TURNS, NUM_PLAYERS

# Role names
VILLAGER = "Villager"
WEREWOLF = "Werewolf"
SEER = "Seer"
DOCTOR = "Doctor"


def group_and_format_observations(observations):
  """Groups observations by round and formats them for output.

  Args:
      observations: A list of strings, where each string starts with "Round X:".

  Returns:
      A list of strings, where each string represents the formatted observations
      for a round.
  """

  grouped = {}
  for obs in observations:
    round_num = int(obs.split(":", 1)[0].split()[1])
    obs_text = obs.split(":", 1)[1].strip().replace('"', "")
    grouped.setdefault(round_num, []).append(obs_text)

  formatted_obs = []
  for round_num, round_obs in sorted(grouped.items()):
    formatted_round = f"Round {round_num}:\n"
    formatted_round += "\n".join(f"   - {obs}" for obs in round_obs)
    formatted_obs.append(formatted_round)

  return formatted_obs


# JSON serializer that works for nested classes
class JsonEncoder(json.JSONEncoder):

  def default(self, o):
    if isinstance(o, enum.Enum):
      return o.value
    if isinstance(o, set):
      return list(o)
    return o.__dict__

def to_dict(o: Any) -> Union[Dict[str, Any], List[Any], Any]:
  return json.loads(JsonEncoder().encode(o))

class GameView:
  """Represents the state of the game for each player."""

  def __init__(
      self,
      round_number: int,
      current_players: List[str],
      other_wolf: Optional[str] = None,
  ):
    self.round_number: int = round_number
    self.current_players: List[str] = current_players
    self.debate: List[tuple[str, str]] = []
    self.other_wolf: Optional[str] = other_wolf

  def update_debate(self, author: str, dialogue: str):
    """Adds a new dialogue entry to the debate."""
    self.debate.append((author, dialogue))

  def clear_debate(self):
    """Clears all entries from the debate."""
    self.debate.clear()

  def remove_player(self, player_to_remove: str):
    """Removes a player from the list of current players."""
    if player_to_remove not in self.current_players:
      print(
          f"Player {player_to_remove} not in current players:"
          f" {self.current_players}"
      )
    self.current_players.remove(player_to_remove)

  def to_dict(self) -> Any:
    return to_dict(self)

  @classmethod
  def from_json(cls, data: Dict[Any, Any]):
    return cls(**data)


class Player(Deserializable):
  """Represents a player in the game."""

  def __init__(
      self,
      name: str,
      role: str,
      model: Optional[str] = None,
      personality: Optional[str] = "",
  ):
    self.name = name
    self.role = role
    self.personality = personality
    self.model = model
    self.observations: List[str] = []
    self.bidding_rationale = ""
    self.gamestate: Optional[GameView] = None

  def initialize_game_view(
      self, round_number, current_players, other_wolf=None
  ) -> None:
    self.gamestate = GameView(round_number, current_players, other_wolf)

  def _add_observation(self, observation: str):
    """Adds an observation for the given round."""
    if not self.gamestate:
      raise ValueError(
          "GameView not initialized. Call initialize_game_view() first."
      )

    self.observations.append(
        f"Round {self.gamestate.round_number}: {observation}"
    )

  def add_announcement(self, announcement: str):
    """Adds the current game announcement to the player's observations."""
    self._add_observation(f"Moderator Announcement: {announcement}")

  def _get_game_state(self) -> Dict[str, Any]:
    """Gets the current game state from the player's perspective."""
    if not self.gamestate:
      raise ValueError(
          "GameView not initialized. Call initialize_game_view() first."
      )

    remaining_players = [
        f"{player} (You)" if player == self.name else player
        for player in self.gamestate.current_players
    ]
    random.shuffle(remaining_players)
    formatted_debate = [
        f"{author} (You): {dialogue}"
        if author == self.name
        else f"{author}: {dialogue}"
        for author, dialogue in self.gamestate.debate
    ]

    formatted_observations = group_and_format_observations(self.observations)

    return {
        "name": self.name,
        "role": self.role,
        "round": self.gamestate.round_number,
        "observations": formatted_observations,
        "remaining_players": ", ".join(remaining_players),
        "debate": formatted_debate,
        "bidding_rationale": self.bidding_rationale,
        "debate_turns_left": MAX_DEBATE_TURNS - len(formatted_debate),
        "personality": self.personality,
        "num_players": NUM_PLAYERS,
        "num_villagers": NUM_PLAYERS - 4, 
    }

  def _generate_action(
      self,
      action: str,
      options: Optional[List[str]] = None,
  ) -> tuple[Any | None, LmLog]:
    """Helper function to generate player actions."""
    game_state = self._get_game_state()
    if options:
      game_state["options"] = (", ").join(options)
    prompt_template, response_schema = ACTION_PROMPTS_AND_SCHEMAS[action]

    result_key, allowed_values = (
        (action, options)
        if action in ["vote", "remove", "investigate", "protect", "bid"]
        else (None, None)
    )

    # Set temperature based on allowed_values
    temperature = 0.5 if allowed_values else 1.0

    return generate(
        prompt_template,
        response_schema,
        game_state,
        model=self.model,
        temperature=temperature,
        allowed_values=allowed_values,
        result_key=result_key,
    )

  def vote(self) -> tuple[str | None, LmLog]:
    """Vote for a player."""
    if not self.gamestate:
      raise ValueError(
          "GameView not initialized. Call initialize_game_view() first."
      )
    options = [
        player
        for player in self.gamestate.current_players
        if player != self.name
    ]
    random.shuffle(options)
    vote, log = self._generate_action("vote", options)
    if vote is not None and len(self.gamestate.debate) == MAX_DEBATE_TURNS:
      self._add_observation(
          f"After the debate, I voted to remove {vote} from the game."
      )
    return vote, log

  def bid(self) -> tuple[int | None, LmLog]:
    """Place a bid."""
    bid, log = self._generate_action("bid", options=["0", "1", "2", "3", "4"])
    if bid is not None:
      bid = int(bid)
      self.bidding_rationale = log.result.get("reasoning", "")
    return bid, log

  def debate(self) -> tuple[str | None, LmLog]:
    """Engage in the debate."""
    result, log = self._generate_action("debate", [])
    if result is not None:
      say = result.get("say", None)
      return say, log
    return result, log

  def summarize(self) -> tuple[str | None, LmLog]:
    """Summarize the game state."""
    result, log = self._generate_action("summarize", [])
    if result is not None:
      summary = result.get("summary", None)
      if summary is not None:
        summary = summary.strip('"')
        self._add_observation(f"Summary: {summary}")
      return summary, log
    return result, log

  def to_dict(self) -> Any:
    return to_dict(self)

  @classmethod
  def from_json(cls, data: Dict[Any, Any]):
    name = data["name"]
    role = data["role"]
    model = data.get("model", None)
    o = cls(name=name, role=role, model=model)
    o.gamestate = data.get("gamestate", None)
    o.bidding_rationale = data.get("bidding_rationale", "")
    o.observations = data.get("observations", [])
    return o


class Villager(Player):
  """Represents a Villager in the game."""

  def __init__(
      self,
      name: str,
      model: Optional[str] = None,
      personality: Optional[str] = None,
  ):
    super().__init__(
        name=name, role=VILLAGER, model=model, personality=personality
    )

  @classmethod
  def from_json(cls, data: dict[Any, Any]):
    name = data["name"]
    model = data.get("model", None)
    o = cls(name=name, model=model)
    o.gamestate = data.get("gamestate", None)
    o.bidding_rationale = data.get("bidding_rationale", "")
    o.observations = data.get("observations", [])
    return o


class Werewolf(Player):
  """Represents a Werewolf in the game."""

  def __init__(
      self,
      name: str,
      model: Optional[str] = None,
      personality: Optional[str] = None,
  ):
    super().__init__(
        name=name, role=WEREWOLF, model=model, personality=personality
    )

  def _get_game_state(self, **kwargs) -> Dict[str, Any]:
    """Gets the current game state, including werewolf-specific context."""
    state = super()._get_game_state(**kwargs)
    state["werewolf_context"] = self._get_werewolf_context()
    return state

  def eliminate(self) -> tuple[str | None, "LmLog"]:
    """Choose a player to eliminate."""
    if not self.gamestate:
      raise ValueError(
          "GameView not initialized. Call initialize_game_view() first."
      )

    options = [
        player
        for player in self.gamestate.current_players
        if player != self.name and player != self.gamestate.other_wolf
    ]
    random.shuffle(options)
    eliminate, log = self._generate_action("remove", options)
    return eliminate, log

  def _get_werewolf_context(self):
    if not self.gamestate:
      raise ValueError(
          "GameView not initialized. Call initialize_game_view() first."
      )

    if self.gamestate.other_wolf in self.gamestate.current_players:
      context = f"\n- The other Werewolf is {self.gamestate.other_wolf}."
    else:
      context = (
          f"\n- The other Werewolf, {self.gamestate.other_wolf}, was exiled by"
          " the Villagers. Only you remain."
      )

    return context

  @classmethod
  def from_json(cls, data: dict[Any, Any]):
    name = data["name"]
    model = data.get("model", None)
    o = cls(name=name, model=model)
    o.gamestate = data.get("gamestate", None)
    o.bidding_rationale = data.get("bidding_rationale", "")
    o.observations = data.get("observations", [])
    return o


class Seer(Player):
  """Represents a Seer in the game."""

  def __init__(
      self,
      name: str,
      model: Optional[str] = None,
      personality: Optional[str] = None,
  ):
    super().__init__(name=name, role=SEER, model=model, personality=personality)
    self.previously_unmasked: Dict[str, str] = {}

  def unmask(self) -> tuple[str | None, LmLog]:
    """Choose a player to unmask."""
    if not self.gamestate:
      raise ValueError(
          "GameView not initialized. Call initialize_game_view() first."
      )

    options = [
        player
        for player in self.gamestate.current_players
        if player != self.name and player not in self.previously_unmasked.keys()
    ]
    random.shuffle(options)
    return self._generate_action("investigate", options)

  def reveal_and_update(self, player, role):
    self._add_observation(
        f"During the night, I decided to investigate {player} and learned they are a {role}."
    )
    self.previously_unmasked[player] = role

  @classmethod
  def from_json(cls, data: dict[Any, Any]):
    name = data["name"]
    model = data.get("model", None)
    o = cls(name=name, model=model)
    o.previously_unmasked = data.get("previously_unmasked", {})
    o.gamestate = data.get("gamestate", None)
    o.bidding_rationale = data.get("bidding_rationale", "")
    o.observations = data.get("observations", [])
    return o


class Doctor(Player):
  """Represents a Doctor in the game."""

  def __init__(
      self,
      name: str,
      model: Optional[str] = None,
      personality: Optional[str] = None,
  ):
    super().__init__(
        name=name, role=DOCTOR, model=model, personality=personality
    )

  def save(self) -> tuple[str | None, LmLog]:
    """Choose a player to protect."""
    if not self.gamestate:
      raise ValueError(
          "GameView not initialized. Call initialize_game_view() first."
      )

    options = list(self.gamestate.current_players)
    random.shuffle(options)
    protected, log = self._generate_action("protect", options)
    if protected is not None:
      self._add_observation(f"During the night, I chose to protect {protected}")
    return protected, log

  @classmethod
  def from_json(cls, data: dict[Any, Any]):
    name = data["name"]
    model = data.get("model", None)
    o = cls(name=name, model=model)
    o.gamestate = data.get("gamestate", None)
    o.bidding_rationale = data.get("bidding_rationale", "")
    o.observations = data.get("observations", [])
    return o


class Round(Deserializable):
  """Represents a round of gameplay in Werewolf.

  Attributes:
    players: List of player names in this round.
    eliminated: Who the werewolves killed during the night phase.
    unmasked: Who the Seer unmasked during the night phase.
    protected: Who the Doctor saved during the night phase.
    exiled: Who the players decided to exile after the debate.
    debate: List of debate tuples of player name and what they said during the
      debate.
    votes:  Who each player voted to exile after each line of dialogue in the
      debate.
    bids: What each player bid to speak next during each turn in the debate.
    success (bool): Indicates whether the round was completed successfully.

  Methods:
    to_dict: Returns a dictionary representation of the round.
  """

  def __init__(self):
    self.players: List[str] = []
    self.eliminated: str | None = None
    self.unmasked: str | None = None
    self.protected: str | None = None
    self.exiled: str | None = None
    self.debate: List[Tuple[str, str]] = []
    self.votes: List[Dict[str, str]] = []
    self.bids: List[Dict[str, int]] = []
    self.success: bool = False

  def to_dict(self):
    return to_dict(self)

  @classmethod
  def from_json(cls, data: Dict[Any, Any]):
    o = cls()
    o.players = data["players"]
    o.eliminated = data.get("eliminated", None)
    o.unmasked = data.get("unmasked", None)
    o.protected = data.get("protected", None)
    o.exiled = data.get("exiled", None)
    o.debate = data.get("debate", [])
    o.votes = data.get("votes", [])
    o.bids = data.get("bids", [])
    o.success = data.get("success", False)
    return o


class State(Deserializable):
  """Represents a game session.

  Attributes:
    session_id: Unique identifier for the game session.
    players: List of players in the game.
    seer: The player with the seer role.
    doctor: The player with the doctor role.
    villagers: List of players with the villager role.
    werewolves: List of players with the werewolf role.
    rounds: List of Rounds in the game.
    error_message: Contains an error message if the game failed during
      execution.
    winner: Villager or Werewolf

  Methods:
    to_dict: Returns a dictionary representation of the game.
  """

  def __init__(
      self,
      session_id: str,
      seer: Seer,
      doctor: Doctor,
      villagers: List[Villager],
      werewolves: List[Werewolf],
  ):
    self.session_id: str = session_id
    self.seer: Seer = seer
    self.doctor: Doctor = doctor
    self.villagers: List[Villager] = villagers
    self.werewolves: List[Werewolf] = werewolves
    self.players: Dict[str, Player] = {
        player.name: player
        for player in self.villagers
        + self.werewolves
        + [self.doctor, self.seer]
    }
    self.rounds: List[Round] = []
    self.error_message: str = ""
    self.winner: str = ""

  def to_dict(self):
    return to_dict(self)

  @classmethod
  def from_json(cls, data: Dict[Any, Any]):
    werewolves = []
    for w in data.get("werewolves", []):
      werewolves.append(Werewolf.from_json(w))

    villagers = []
    for v in data.get("villagers", []):
      villagers.append(Villager.from_json(v))

    doctor = Doctor.from_json(data.get("doctor"))
    seer = Seer.from_json(data.get("seer"))

    players = {}
    for p in werewolves + villagers + [doctor, seer]:
      players[p.name] = p

    o = cls(
        data.get("session_id", ""),
        seer,
        doctor,
        villagers,
        werewolves,
    )
    rounds = []
    for r in data.get("rounds", []):
      rounds.append(Round.from_json(r))

    o.rounds = rounds
    o.error_message = data.get("error_message", "")
    o.winner = data.get("winner", "")
    return o


class VoteLog(Deserializable):

  def __init__(self, player: str, voted_for: str, log: LmLog):
    self.player = player
    self.voted_for = voted_for
    self.log = log

  def to_dict(self):
    return to_dict(self)

  @classmethod
  def from_json(cls, data: Dict[Any, Any]):
    player = data.get("player", None)
    voted_for = data.get("voted_for", None)
    log = LmLog.from_json(data.get("log", None))
    return cls(player, voted_for, log)


class RoundLog(Deserializable):
  """Represents the logs of a round of gameplay in Werewolf.

  Attributes:
    eliminate: Logs from the eliminate action taken by werewolves.
    investigate: Log from the invesetigate action taken by the seer.
    protect: Log from the protect action taken by the doctor.
    bid: Logs from the bidding actions. The 1st element in the list is the bidding logs
      for the 1st debate turn, the 2nd element is the logs for the 2nd debate
      turn, and so on. Every player bids to speak on every turn, so the element
      is a list too. The tuple contains the name of the player and the log of
      their bidding.
    debate: Logs of the debates. Each round has multiple debate turbns, so it's a
      list. Each element is a tuple - the 1st element is the name of the player
      who spoke at this turn, and the 2nd element is the log.
    vote: Log of the votes. A list of logs, one for every player who voted. The
      1st element of the tuple is the name of the player, and the 2nd element is
      the log.
    summaries: Logs from the summarize step. Every player summarizes their
      observations at the end of a round before they vote. Each element is a
      tuple where the 1st element is the name of the player, and the 2nd element
      is the log
  """

  def __init__(self):
    self.eliminate: LmLog | None = None
    self.investigate: LmLog | None = None
    self.protect: LmLog | None = None
    self.bid: List[List[Tuple[str, LmLog]]] = []
    self.debate: List[Tuple[str, LmLog]] = []
    self.votes: List[List[VoteLog]] = []
    self.summaries: List[Tuple[str, LmLog]] = []

  def to_dict(self):
    return to_dict(self)

  @classmethod
  def from_json(cls, data: Dict[Any, Any]):
    o = cls()

    eliminate = data.get("eliminate", None)
    investigate = data.get("investigate", None)
    protect = data.get("protect", None)

    if eliminate:
      o.eliminate = LmLog.from_json(eliminate)
    if investigate:
      o.investigate = LmLog.from_json(investigate)
    if protect:
      o.protect = LmLog.from_json(protect)

    for votes in data.get("votes", []):
      v_logs = []
      o.votes.append(v_logs)
      for v in votes:
        v_logs.append(VoteLog.from_json(v))

    for r in data.get("bid", []):
      r_logs = []
      o.bid.append(r_logs)
      for player in r:
        r_logs.append((player[0], LmLog.from_json(player[1])))

    for player in data.get("debate", []):
      o.debate.append((player[0], LmLog.from_json(player[1])))

    for player in data.get("summaries", []):
      o.summaries.append((player[0], LmLog.from_json(player[1])))

    return o
