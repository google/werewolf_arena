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

import random
import traceback
from typing import List, Tuple
import itertools
import pandas as pd
import os
import datetime

from absl import flags
import tqdm

from werewolf import logging
from werewolf import game
from werewolf.model import Doctor
from werewolf.model import SEER
from werewolf.model import Seer
from werewolf.model import State
from werewolf.model import Villager
from werewolf.model import WEREWOLF
from werewolf.model import Werewolf
from werewolf.config import get_player_names

_RUN_GAME = flags.DEFINE_boolean("run", False, "Runs a single game.")
_RESUME = flags.DEFINE_boolean("resume", False, "Resumes games.")
_EVAL = flags.DEFINE_boolean("eval", False, "Collect eval data by running many games.")
_NUM_GAMES = flags.DEFINE_integer(
    "num_games", 2, "Number of games to run used with eval."
)
_VILLAGER_MODELS = flags.DEFINE_list(
    "v_models", "", "The model used for villagers values are: flash, pro, gpt4"
)
_WEREWOLF_MODELS = flags.DEFINE_list(
    "w_models", "", "The model used for werewolves values are: flash, pro, gpt4"
)
_ARENA = flags.DEFINE_boolean(
    "arena", False, "Only run games using different models for villagers and werewolves"
)
_THREADS = flags.DEFINE_integer("threads", 2, "Number of threads to run.")

DEFAULT_WEREWOLF_MODELS = ["flash", "pro1.5"]
DEFAULT_VILLAGER_MODELS = ["flash", "pro1.5"]
RESUME_DIRECTORIES = []

model_to_id = {
    "pro1.5": "gemini-1.5-pro-preview-0514",
    "flash": "gemini-1.5-flash-001",
    "pro1": "gemini-pro",
    "gpt4": "gpt-4-turbo-2024-04-09",
    "gpt4o": "gpt-4o-2024-05-13",
    "gpt3.5": "gpt-3.5-turbo-0125",
}


def initialize_players(
    villager_model: str, werewolf_model: str
) -> Tuple[Seer, Doctor, List[Villager], List[Werewolf]]:
    """Assigns roles to players and initializes their game view."""

    player_names = get_player_names()
    random.shuffle(player_names)

    seer = Seer(
        name=player_names.pop(),
        model=villager_model,
        # personality="You are cunning.",
    )
    doctor = Doctor(name=player_names.pop(), model=villager_model)
    werewolves = [
        Werewolf(name=player_names.pop(), model=werewolf_model) for _ in range(2)
    ]
    villagers = [Villager(name=name, model=villager_model) for name in player_names]

    # Initialize game view for all players
    for player in [seer, doctor] + werewolves + villagers:
        other_wolf = (
            next((w.name for w in werewolves if w != player), None)
            if isinstance(player, Werewolf)
            else None
        )
        tqdm.tqdm.write(f"{player.name} has role {player.role}")
        player.initialize_game_view(
            current_players=player_names
            + [seer.name, doctor.name]
            + [w.name for w in werewolves],
            round_number=0,
            other_wolf=other_wolf,
        )

    return seer, doctor, villagers, werewolves


def resume_game(directory: str) -> bool:
    state, logs = logging.load_game(directory)

    # remove the failed round and resume from the beginning of that round.
    last_round = state.rounds[-1]
    if not last_round.success:
        state.rounds.pop()
        logs.pop()
    # Reset the error state
    state.error_message = ""

    if not state.rounds:
        werewolves = []
        for p in state.players.values():
            p.initialize_game_view(
                round_number=0,
                current_players=list(state.players.keys()),
            )
            p.observations = []

            if p.role == WEREWOLF:
                werewolves.append(p)

            if p.role == SEER:
                p.previously_unmasked = {}

        if len(werewolves) == 2:
            werewolves[0].gamestate.other_wolf = werewolves[1].name
            werewolves[1].gamestate.other_wolf = werewolves[0].name
    else:
        # Update the GameView for every active player
        werewolves = []
        for p in state.rounds[-1].players:
            player = state.players.get(p, None)
            if player:
                player.initialize_game_view(
                    round_number=len(state.rounds),
                    current_players=state.rounds[-1].players[:],
                )

                # Remove the observation from the failed round for all active players
                failed_round = len(state.rounds)
                player.observations = [
                    o
                    for o in player.observations
                    if not o.startswith(f"Round {failed_round}")
                ]

                if player.role == WEREWOLF:
                    werewolves.append(player)

                # update the seer's unmasking history
                unmasking_history = {}
                if player.role == SEER:
                    for r in state.rounds:
                        if r.unmasked:
                            unmasked_player = state.players.get(r.unmasked, None)
                            if unmasked_player:
                                unmasking_history[r.unmasked] = unmasked_player.role
                    player.previously_unmasked = unmasking_history

        if len(werewolves) == 2:
            werewolves[0].gamestate.other_wolf = werewolves[1].name
            werewolves[1].gamestate.other_wolf = werewolves[0].name

    gm = game.GameMaster(state, num_threads=_THREADS.value)
    gm.logs = logs
    try:
        gm.run_game()
    except Exception as e:
        state.error_message = traceback.format_exc()
    logging.save_game(state, gm.logs, directory)
    return not state.error_message


def resume_games(directories: list[str]):
    successful_resumes = []
    failed_resumes = []
    invalid_resumes = []
    for i in tqdm.tqdm(range(len(directories)), desc="Games"):
        d = directories[i]
        try:
            success = resume_game(d)
            if success:
                successful_resumes.append(d)
            else:
                failed_resumes.append(d)
        except Exception as e:
            if "not found" in str(e):
                invalid_resumes.append(d)
            print(f"Error encountered during resume: {e}")

    print(
        f"Successful resumes: {successful_resumes}.\nFailed resumes:"
        f" {failed_resumes}\nInvalid resumes(no partial game found):"
        f" {invalid_resumes}"
    )


def run_game(
    werewolf_model: str,
    villager_model: str,
) -> Tuple[str, str]:
    """Runs a single game of Werewolf.

    Returns: (winner, log_dir)
    """
    seer, doctor, villagers, werewolves = initialize_players(
        villager_model, werewolf_model
    )
    session_id = "10"  # You might want to make this unique per game
    state = State(
        villagers=villagers,
        werewolves=werewolves,
        seer=seer,
        doctor=doctor,
        session_id=session_id,
    )

    gamemaster = game.GameMaster(state, num_threads=_THREADS.value)
    winner = None
    try:
        winner = gamemaster.run_game()
    except Exception as e:
        state.error_message = traceback.format_exc()
        print(f"Error encountered during game: {e}")

    log_directory = logging.log_directory()
    logging.save_game(state, gamemaster.logs, log_directory)
    print(f"Game logs saved to: {log_directory}")

    return winner, log_directory


def run() -> None:
    villager_models = _VILLAGER_MODELS.value or DEFAULT_VILLAGER_MODELS
    werewolf_models = _WEREWOLF_MODELS.value or DEFAULT_WEREWOLF_MODELS
    v_ids = [model_to_id[m] for m in villager_models]
    w_ids = [model_to_id[m] for m in werewolf_models]
    model_combinations = list(itertools.product(v_ids, w_ids))
    if _RUN_GAME.value:
        villager_model, werewolf_model = model_combinations[0]
        print(f"Villagers: {villager_model} versus Werwolves:  {werewolf_model}")
        run_game(
            werewolf_model=werewolf_model,
            villager_model=villager_model,
        )
    elif _EVAL.value:
        results = []
        for villager_model, werewolf_model in model_combinations:
            # only run games using different models in the arena mode
            if villager_model == werewolf_model and _ARENA.value:
                continue
            print(
                f"Running games with Villagers: {villager_model} and"
                f" Werewolves:{werewolf_model}"
            )
            for _ in tqdm.tqdm(range(_NUM_GAMES.value), desc="Games"):
                winner, log_dir = run_game(
                    werewolf_model=werewolf_model,
                    villager_model=villager_model,
                )
                results.append([villager_model, werewolf_model, winner, log_dir])

        df = pd.DataFrame(
            results, columns=["VillagerModel", "WerewolfModel", "Winner", "Log"]
        )
        print("######## Eval results ########")
        print(df)

        pacific_timezone = datetime.timezone(datetime.timedelta(hours=-8))
        timestamp = datetime.datetime.now(pacific_timezone).strftime("%Y%m%d_%H%M%S")
        csv_file = f"{os.getcwd()}/logs/eval_results_{timestamp}.csv"
        df.to_csv(csv_file)
        print(f"Wrote eval results to {csv_file}")

    elif _RESUME.value:
        resume_games(RESUME_DIRECTORIES)
