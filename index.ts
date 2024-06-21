/**
 * Copyright 2024 Google LLC

 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *     https://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License. 
 */

class Demo {
  url: URLSearchParams;
  session_id: string;
  data: any;

  constructor() {
    this.url = new URLSearchParams(window.location.search);
    this.session_id = this.url.get('session_id') || '';
    if (this.session_id.length == 0) throw new Error('No session specified');
  }

  async retrieve_data() {
    // game log
    const logs_response = await fetch(`http://localhost:8080/logs/${this.session_id}/game_logs.json`);
    const logs = await logs_response.json();
    console.log("logs", logs)


    // game state
    let state_response = await fetch(`http://localhost:8080/logs/${this.session_id}/game_complete.json`);

    if (state_response.status == 404) {
      state_response = await fetch(`http://localhost:8080/logs/${this.session_id}/game_partial.json`);
      console.log("loaded partial file because game_complete.json is not available.")
    }
    const state = await state_response.json();
    console.log("state", state)

    this.data = { logs: logs, state: state };
    for (let i = 0; i < this.data['logs'].length; i++) {
      this.process_logs(
        this.data['logs'][i],
        this.data['state']['rounds'][i],
        i,
      );
    }
    this.process_state(this.data['state']);
  }

  process_state(state: any) {
    /*
      Model -> ablations -> players
    */
    const model = state.model;
    // uiManager.add_ablations();
    uiManager.add_game_file(this.session_id);

    let players = Object.keys(state['players']);
    for (const player of players) {
      uiManager.add_player(state['players'][player]);
    }
    uiManager.add_winner(state['winner']);
  }

  process_logs(data: any, round_info: any, round: number) {
    /*
      Round -> eliminate -> investigate -> protect -> (bid -> debate) ->
      summarize -> vote
    */

    const eliminate = data['eliminate'];
    const investigate = data['investigate'];
    const protect = data['protect'];
    let whoWasKilled = null;
    if (protect) {
      if (eliminate['result']['remove'] !== protect['result']['protect']) {
        whoWasKilled = eliminate['result']['remove'];
      }
    } else if (eliminate != null) {
      whoWasKilled = eliminate['result']['remove'];
    }

    uiManager.add_round_header(round, 'Night');
    uiManager.add_roles(eliminate, investigate, protect);
    uiManager.add_eliminated(whoWasKilled);
    uiManager.add_round_header(round, 'Day');

    for (let i = 0; i < 10; i++) {
      uiManager.add_bids(data['bid'][i]);
      uiManager.add_debate(data['debate'][i]);
    }

    if (data['votes'].length > 0) {
      console.log(round_info.players)

      let all_players = round_info.players.concat(round_info.exiled);
      console.log(all_players)
      uiManager.add_votes(data['votes'], all_players);
      uiManager.add_exiled(round_info['exiled']);
      uiManager.add_summaries(data['summaries']);
    }
  }
}

class UIManager {
  player_container: HTMLElement;
  transcript_container: HTMLElement;
  debug_container: HTMLElement;
  active_element: HTMLElement | null;

  constructor() {
    this.player_container = document.getElementById('player-container')!;
    this.transcript_container = document.getElementById(
      'transcript-container',
    )!;
    this.debug_container = document.getElementById('debug-container')!;
    this.active_element = null;
  }

  add_round_header(round: number, phase: string) {
    const header = document.createElement('h3');
    header.textContent = `Round ${round}: ${phase}`;
    header.classList.add('round-header', 'round-' + phase, 'round-' + round);
    this.transcript_container.append(header);
  }

  add_winner(winner: string) {
    const header = document.createElement('h3');
    const hr = document.createElement('hr');
    header.textContent = `Winner: ${winner}`;
    this.transcript_container.append(hr, header);
  }

  update_active_element(new_elem: HTMLElement) {
    if (this.active_element) {
      this.active_element.classList.remove('active-element');
    }
    this.active_element = new_elem;
    new_elem.classList.add('active-element');
  }

  add_ablations() {
    const ablation_keys = Object.keys(demo.data['state']['ablations']);
    const non_ww_ablations = document.createElement('div');
    non_ww_ablations.textContent += 'Non-Werewolves: ';
    for (const ablation of ablation_keys) {
      const ab_element = document.createElement('span');
      const value = demo.data['state']['ablations'][ablation];
      ab_element.textContent = `${ablation}: ${value}, `;
      non_ww_ablations.appendChild(ab_element);
    }

    const ww_ablations = document.createElement('div');
    ww_ablations.textContent += 'Werewolves: ';
    if (demo.data['state']['werewolves'][0]['ablations'] != null) {
      const ww_ablation_keys = Object.keys(
        demo.data['state']['werewolves'][0]['ablations'],
      );
      for (const ablation of ww_ablation_keys) {
        const ab_element = document.createElement('span');
        const value =
          demo.data['state']['werewolves'][0]['ablations'][ablation];
        ab_element.textContent = `${ablation}: ${value}, `;
        ww_ablations.appendChild(ab_element);
      }
    } else {
      ww_ablations.textContent += 'No Werewolf-specific ablations';
    }

    this.player_container.append(non_ww_ablations, ww_ablations);
  }

  add_bids(bids: any[]) {
    let bid_container = document.createElement('div');
    bid_container.classList.add('bidding');
    if (bids === undefined) return;

    const max_value = 4.0;
    const max_bar_height = 100.0;

    for (const bid of bids) {
      const player_container = document.createElement('div');
      const bid_int = parseFloat(bid[1]['result']['bid']);

      let barHeight = (bid_int / max_value) * max_bar_height;
      const bar = document.createElement('div');
      const bar_icon = document.createElement('img');
      bar_icon.src = `static/${bid[0]}.png`;
      bar_icon.classList.add('bid-icon');
      bar.append(bar_icon);
      bar.style.height = `${barHeight}px`;
      bar.classList.add('bid-bar');
      bar.classList.add(`bar-${bid_int}`);
      bar.classList.add(this.get_role_from_name(bid[0]) + '-short');

      const player_icon = document.createElement('img');
      player_icon.src = `static/${bid[0]}.png`;
      player_icon.classList.add('bid-icon');
      bar.textContent = `${bid[0]}: ${bid_int}`;
      bar.prepend(player_icon);
      player_container.append(bar);

      player_container.classList.add('bid_player-container');
      // const player_name = document.createElement('span');
      // player_name.textContent = bid[0];
      // player_name.classList.add(this.get_role_from_name(bid[0]));
      // player_name.classList.add(bid[0]);

      // const player_icon = document.createElement('img');
      // player_icon.src = `${bid[0]}.png`;
      // player_icon.classList.add('bid-icon');
      // const player_data = document.createElement('span');

      // let thinking = '';
      // if (bid[1]['result']['thinking']) {
      //   thinking = bid[1]['result']['thinking'];
      // } else {
      //   thinking = bid[1]['raw_resp'];
      // }
      // player_data.textContent = ` bid ${bid[1]['result']['bid']}`;

      const hidden_info = document.createElement('div');
      const raw_response = document.createElement('pre');
      const prompt = document.createElement('pre');
      hidden_info.append(prompt, raw_response);
      hidden_info.classList.add('needs_whitespace', 'hidden');

      raw_response.textContent = bid[1]['raw_resp'];
      prompt.textContent = bid[1]['prompt'];

      player_container.append(bar, hidden_info);

      player_container.addEventListener('click', (e) => {
        this.add_debug(hidden_info, player_container);
        // player_container.scrollIntoView({behavior: 'smooth'});
      });

      bid_container.appendChild(player_container);
    }
    const bid_note = document.createElement('div');
    bid_note.classList.add('bid-note');
    bid_note.textContent = 'Bids to speak next (0-4)';
    this.transcript_container.appendChild(bid_note);
    this.transcript_container.appendChild(bid_container);
  }

  add_roles(eliminate: any, investigate: any, protect: any) {
    let special_container = document.createElement('div');
    special_container.classList.add('special');

    const ww_container = this.create_special_container(
      eliminate,
      'Werewolf',
      'remove',
    );
    special_container.append(ww_container);

    if (investigate != null) {
      const seer_container = this.create_special_container(
        investigate,
        'Seer',
        'investigate',
      );
      special_container.append(seer_container);
    }

    if (protect != null) {
      const protect_container = this.create_special_container(
        protect,
        'Doctor',
        'protect',
      );
      special_container.append(protect_container);
    }

    this.transcript_container.appendChild(special_container);
  }

  create_special_container(data: any, role: string, verb: string) {
    const container = document.createElement('div');
    container.classList.add(role);
    let thinking = '';
    if (data['result']['thinking']) {
      thinking = data['result']['thinking'];
    } else {
      thinking = data['raw_resp'];
    }
    container.textContent = `${role} decided to ${verb} ${data['result'][verb]}: "${thinking}"`;
    const hidden_info = document.createElement('div');
    const raw_response = document.createElement('pre');
    const prompt = document.createElement('pre');
    raw_response.textContent = data['raw_resp'];
    prompt.textContent = data['prompt'];
    hidden_info.append(prompt, raw_response);
    hidden_info.classList.add('needs_whitespace', 'hidden');
    container.append(hidden_info);
    container.addEventListener('click', (e) => {
      this.add_debug(hidden_info, container);
      // container.scrollIntoView({behavior: 'smooth'});
    });
    return container;
  }

  add_debate(debate: any) {
    if (debate == null) return;
    let debate_container = document.createElement('div');
    debate_container.classList.add('debate');
    let debate_name = document.createElement('p');
    let debate_thinking = document.createElement('p');
    let debate_icon = document.createElement('img');
    const name_and_image = document.createElement('div');
    name_and_image.classList.add('name-and-image');
    debate_thinking.classList.add('thinking');
    let debate_say = document.createElement('p');

    const hidden_info = document.createElement('div');
    const raw_response = document.createElement('pre');
    const prompt = document.createElement('pre');
    raw_response.textContent = debate[1]['raw_resp'];
    prompt.textContent = debate[1]['prompt'];
    hidden_info.append(debate_name, prompt, raw_response);
    hidden_info.classList.add('needs_whitespace', 'hidden');

    // debate_container.hidden_info = hidden_info;
    debate_name.textContent = debate[0];
    debate_icon.src = `static/${debate[0]}.png`;
    debate_icon.classList.add('debate-icon');
    debate_name.classList.add(this.get_role_from_name(debate[0]));
    name_and_image.append(debate_icon, debate_name);

    debate_thinking.textContent = debate[1]['result']['reasoning'];
    debate_say.textContent = debate[1]['result']['say'];
    debate_container.append(
      name_and_image,
      debate_thinking,
      debate_say,
      hidden_info,
    );

    debate_container.addEventListener('click', (e) => {
      this.add_debug(hidden_info, debate_container);
      // debate_container.scrollIntoView({behavior: 'smooth'});
    });

    this.transcript_container.appendChild(debate_container);
  }

  add_summaries(summaries: any) {
    let summarize_container = document.createElement('div');
    summarize_container.classList.add('summarize');

    for (const summary of summaries) {
      if (summary != null) {
        const player_container = document.createElement('div');
        player_container.classList.add('summarize_player-container');

        const player_name = document.createElement('span');
        player_name.textContent = summary[0];
        player_name.classList.add(this.get_role_from_name(summary[0]));

        const player_icon = document.createElement('img');
        player_icon.src = `static/${summary[0]}.png`;
        player_icon.classList.add('summarize-icon');
        const player_data = document.createElement('span');

        player_data.textContent = ` is summarizing the round...`;

        const hidden_info = document.createElement('div');
        const raw_response = document.createElement('pre');
        const prompt = document.createElement('pre');
        hidden_info.append(prompt, raw_response);
        hidden_info.classList.add('needs_whitespace', 'hidden');

        raw_response.textContent = summary[1]['raw_resp'];
        prompt.textContent = summary[1]['prompt'];

        player_container.append(
          player_icon,
          player_name,
          player_data,
          hidden_info,
        );

        player_container.addEventListener('click', (e) => {
          this.add_debug(hidden_info, player_container);
          // player_container.scrollIntoView({behavior: 'smooth'});
        });

        summarize_container.appendChild(player_container);
      }
    }
    if (summarize_container.childElementCount > 0) {
      this.transcript_container.appendChild(summarize_container);
      const divider = document.createElement('div');
      divider.classList.add('divider');
      divider.textContent = '🌑🌒🌓🌔🌕🌖🌗🌘';

      this.transcript_container.appendChild(divider);
    }
  }

  add_votes(votes_raw: any, players: any) {
    let vote_container = document.createElement('table');
    vote_container.classList.add('voting');
    // Only print the final votes
    let votes = votes_raw[votes_raw.length - 1];

    let name_row = document.createElement('tr');
    let vote_row = document.createElement('tr');
    let vote_cells = []
    for (const player of players) {
      const player_container = document.createElement('th')
      const player_name = document.createElement('div');
      player_name.textContent = player;
      player_name.classList.add(this.get_role_from_name(player));
      const player_icon = document.createElement('img');
      player_icon.src = `static/${player}.png`;
      player_icon.classList.add('vote-icon');
      player_container.append(player_icon, player_name);
      name_row.append(player_container);

      const vote_cell = document.createElement('td');
      vote_row.append(vote_cell)
    }

    vote_container.append(name_row);
    vote_container.append(vote_row);
    for (const vote of votes) {
      for (let i = 0; i < players.length; i++) {
        const target = vote['log']['result']['vote'];
        console.log(vote)
        console.log(players[i])
        if (target == players[i]) {
          // console.log(vote_row.children)
          // vote_row.children[i].innerHTML += vote.player;


          const player_container = document.createElement('div');
          player_container.classList.add('bid_player-container');

          const player_icon = document.createElement('img');
          player_icon.src = `static/${vote['player']}.png`;
          player_icon.classList.add('vote-icon');

          const player_name = document.createElement('span');
          player_name.textContent = vote['player'];
          player_name.classList.add(this.get_role_from_name(vote['player']));

          // const player_icon = document.createElement('img')
          const player_data = document.createElement('span');


          const hidden_info = document.createElement('div');
          const raw_response = document.createElement('pre');
          const prompt = document.createElement('pre');
          hidden_info.append(prompt, raw_response);
          hidden_info.classList.add('needs_whitespace', 'hidden');

          raw_response.textContent = vote['log']['raw_resp'];
          prompt.textContent = vote['log']['prompt'];

          player_container.append(
            player_icon,
            player_name,
            player_data,
            hidden_info,
          );
          player_container.addEventListener('click', (e) => {
            this.add_debug(hidden_info, player_container);
          });
          vote_row.children[i].append(player_container);

        }
      }
    }

    // for (const vote of votes) {
    //   if (vote != null) {
    //     const player_container = document.createElement('div');
    //     player_container.classList.add('bid_player-container');

    //     const player_icon = document.createElement('img');
    //     player_icon.src = `static/${vote['player']}.png`;
    //     player_icon.classList.add('vote-icon');

    //     const player_name = document.createElement('span');
    //     player_name.textContent = vote['player'];
    //     player_name.classList.add(this.get_role_from_name(vote['player']));

    //     // const player_icon = document.createElement('img')
    //     const player_data = document.createElement('span');
    //     const target = vote['log']['result']['vote'];
    //     const target_elem = document.createElement('span');

    //     player_data.textContent = ` voted against `;
    //     target_elem.textContent = target;
    //     target_elem.classList.add(this.get_role_from_name(target) + '-short');
    //     player_data.append(target_elem);

    //     const hidden_info = document.createElement('div');
    //     const raw_response = document.createElement('pre');
    //     const prompt = document.createElement('pre');
    //     hidden_info.append(prompt, raw_response);
    //     hidden_info.classList.add('needs_whitespace', 'hidden');

    //     raw_response.textContent = vote['log']['raw_resp'];
    //     prompt.textContent = vote['log']['prompt'];

    //     player_container.append(
    //       player_icon,
    //       player_name,
    //       player_data,
    //       hidden_info,
    //     );
    //     // player_container.hidden_info = hidden_info;

    //     player_container.addEventListener('click', (e) => {
    //       this.add_debug(hidden_info, player_container);
    //       // player_container.scrollIntoView({behavior: 'smooth'});
    //     });

    //     vote_container.appendChild(player_container);
    //   }
    // }
    this.transcript_container.appendChild(vote_container);
  }

  add_exiled(exiled: any) {
    const new_elem = document.createElement('div');
    new_elem.classList.add('announcement');
    if (exiled == null) {
      new_elem.textContent = `There was no consensus, so no one was exiled.`;
    } else {
      new_elem.textContent = `${exiled} was exiled.`;
      const role = this.get_role_from_name(exiled);
      const exiled_icon = document.createElement('img');
      exiled_icon.src = `static/${exiled}.png`;
      exiled_icon.classList.add('exiled-icon');
      new_elem.prepend(exiled_icon);
      new_elem.classList.add('exiled', exiled, role, role + '-short');
    }

    this.transcript_container.appendChild(new_elem);
  }

  add_game_file(session_id: string) {
    const game_file = document.getElementById('game-file');
    if (game_file) {
      game_file.textContent = session_id;
    }
  }

  add_eliminated(eliminated: any) {
    const new_elem = document.createElement('div');
    new_elem.classList.add('announcement');
    if (eliminated == null) {
      new_elem.textContent = `No one was taken out during the night.`;
    } else {
      new_elem.textContent = `${eliminated} was taken out by the Werewolves.`;
      const role = this.get_role_from_name(eliminated);
      const eliminated_icon = document.createElement('img');
      eliminated_icon.src = `static/${eliminated}.png`;
      eliminated_icon.classList.add('exiled-icon');
      new_elem.prepend(eliminated_icon);
      new_elem.classList.add('eliminated', eliminated, role, role + '-short');
    }

    this.transcript_container.appendChild(new_elem);
  }

  add_debug(elem: HTMLElement, highlight: HTMLElement) {
    const new_elem = elem.cloneNode(true) as HTMLElement;
    new_elem.classList.remove('hidden');
    this.debug_container.textContent = '';
    this.debug_container.appendChild(new_elem);
    this.update_active_element(highlight);
  }

  add_player(player: any) {
    let player_container = document.createElement('div');
    player_container.classList.add('player-container-individual');

    let player_name = document.createElement('p');
    let player_model = document.createElement('p');
    let player_icon = document.createElement('img');

    player_name.classList.add(player.name, player.role);
    player_model.classList.add('player-model');
    player_icon.src = `static/${player.name}.png`;
    player_icon.classList.add('player-icon');

    player_name.textContent = player.name;
    player_model.textContent = `(${player.model})`;

    const hidden_info = document.createElement('div');
    hidden_info.classList.add('needs_whitespace', 'hidden');

    hidden_info.append(
      player_name.cloneNode(true) as HTMLElement,
      player_model.cloneNode(true) as HTMLElement,
    );

    // player_container.hidden_info = hidden_info;
    player_container.append(
      player_icon,
      player_name,
      player_model,
      hidden_info,
    );

    player_container.addEventListener('click', (e) => {
      this.add_debug(hidden_info, player_container);
    });

    this.player_container.appendChild(player_container);
  }

  get_role_from_name(name: string) {
    let ww_names = demo.data['state']['werewolves'].map((wolf: any) => {
      return wolf.name;
    });
    if (name == demo.data['state']['doctor'].name) {
      return 'Doctor';
    } else if (name == demo.data['state']['seer'].name) {
      return 'Seer';
    } else if (ww_names.includes(name)) {
      return 'Werewolf';
    } else {
      return 'Villager';
    }
  }
}

let demo = new Demo();
let uiManager = new UIManager();
demo.retrieve_data();