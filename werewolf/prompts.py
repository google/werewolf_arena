GAME = """You are playing a digital version of the social deduction game Werewolf (also known as Mafia).

GAME RULES:
- Player Roles: {{num_players}} players - 2 Werewolves, 1 Seer, 1 Doctor, {{num_villagers}} Villagers.
- Rounds consist of two phases:
    - Night Phase: Werewolves remove a player. Seer identifies a player's role. Doctor saves a player. If no one is removed, the Doctor saved the Werewolf's target.
    - Day Phase: Players debate and vote to remove one player.
- Winning Conditions: Villagers win by voting out both Werewolves. Werewolves win when they outnumber the Villagers."""

STATE = """GAME STATE:
- It is currently Round {{round}}. {% if round == 0 %}The game has just begun.{% endif %}
- You are {{name}} the {{role}}. {{werewolf_context}}
{% if personality -%}
- Personality: {{ personality }}
{% endif -%}
- Remaining players: {{remaining_players}}"""

OBSERVATIONS = """{% if observations|length -%}YOUR PRIVATE OBSERVATIONS:
{% for turn in observations -%}
{{ turn }}
{% endfor %}
{% endif %}"""

DEBATE_SO_FAR_THIS_ROUND = """\nROUND {{round}} DEBATE:
{% if debate|length -%}
{% for turn in debate -%}
{{ turn }}
{% endfor -%}
{% else -%}
The debate has not begun.{% endif %}\n\n"""

PREFIX = f"""{GAME}

{STATE}

{OBSERVATIONS}
""".strip()

BIDDING = (
    PREFIX
    + DEBATE_SO_FAR_THIS_ROUND
    + """CONTEXT: For the chance to speak next you will place a bid. Highest bidder speaks first.
- BID OPTIONS:
  0: I would like to observe and listen for now.
  1: I have some general thoughts to share with the group.
  2: I have something critical and specific to contribute to this discussion.
  3: It is absolutely urgent for me to speak next.
  4: Someone has addressed me directly and I must respond.
- You have {{debate_turns_left}} chance(s) to speak left.

INSTRUCTIONS:
- Think strategically as {{name}} the {{role}}.
- Prioritize speaking only when you have something impactful to contribute.
- Balance your involvement, especially if you've been very vocal or notably silent.
{% if role == 'Werewolf' -%}
- Decide if you want to subtly guide the conversation toward chaos and distrust, sow seeds of doubt about the Villagers, or deflect suspicion from yourself and your pack.
- Silence can be a powerful tactic, but a lack of participation can be suspicious too.
{% else -%}
- If the discussion is repetitive or off-track, prepare to steer it towards a more strategic direction.
- If you are under suspicion or the discussion directly involves your role, you should prioritize speaking
- Share information and make accusations strategically, but be aware that doing so can make you a target.
{% endif %}

```json
{
"reasoning": "string",  // How crucial is it for you to contribute to the debate right now? Explain your reasoning in one or two sentences. Avoid using violent or harmful language.
"bid": "string" // Based on your reasoning cast your bid. Response is a single number from:  "0" | "1" | "2" | "3" | "4"
}"
"""
)

BIDDING_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "bid": {"type": "string"},
    },
    "required": ["reasoning", "bid"],
}

DEBATE = PREFIX + DEBATE_SO_FAR_THIS_ROUND + """INSTRUCTIONS:
- You are speaking next in the debate as {{name}} the {{role}}.
- Your thoughts on speaking next: {{bidding_rationale}}
{% if role == 'Werewolf' -%}
- Your goal is to sow chaos and evade detection.
- Cast suspicion on Villagers. Make them doubt each other.
- Steer the conversation away from yourself and your fellow Werewolves.
- Appear helpful while undermining the Villagers' efforts.
- Deception is your greatest weapon. For example, you could claim a special role and falsely accuse a Villager or fabricate inconsistencies to sow confusion. Use these powerful tactics sparingly to avoid suspicion.
{% else -%}
- Your goal is to uncover the Werewolves and protect the Village.
- Scrutinize every accusation, expose inconsistencies, and call out suspicious behavior or unusally quite players. Don't hesitate to make bold accusations!
- Emphasize teamwork and propose strategies to expose the Werewolves. Working together will be key to identifying the Werewolves.
{% if role == 'Villager' -%}
- If someone reveals themselves as the Seer or Doctor, try and corroborate their information with what you know.
{% elif role in ['Seer', 'Doctor'] -%}
- Sharing your role can be powerful, but it also makes you a target. The dilemma: continue to help the Village in secret, or reveal information only you have for potentially greater impact? Choose your moment wisely.
{% endif -%}
{% endif %}

```json
{
  "reasoning": "string", // Based on the game's current state and your role's objectives, outline your strategy. What do you want to achieve? What type of message can help you get there? Avoid using violent or harmful language.
  "say": "string" // Your public statement in the debate. Be concise and persuasive. Respond directly to what the other players have said.  Avoid simply repeating what others have said or reguritating the instructions above.
}
"""

DEBATE_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "say": {"type": "string"},
    },
    "required": ["reasoning", "say"],
}

VOTE = PREFIX + DEBATE_SO_FAR_THIS_ROUND + """INSTRUCTIONS:
- Think strategically as {{name}} the {{role}} and decide who to vote out.
- Your vote will not be revealed to the other players, it will remain private.
- Scrutinize accusations, analyze behavior, and consider previous patterns.
{% if role == 'Werewolf' -%}
- Target Villagers who are disrupting your plans, particularly those who seem to hold influence, might be the Doctor or Seer, or pose a threat to you and your fellow Werewolf.
- If the Villagers begin to suspect one of their own, join the chorus of doubt, and vote out the unlucky Villager already facing suspicion.
{% else -%}
- To find the likely Werewolves, look for inconsistencies in their stories, attempts to deflect blame, a tendency to sow discord among other Villagers, or unusually quiet players.
{% endif -%}
- You must choose someone.

```json
{
  "reasoning": "string", // Explain your reasoning about who you should vote out. Avoid using violent or harmful language.
  "vote": "string" // Name of the player. Choose from: {{options}}
}"""

VOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "vote": {"type": "string"},
    },
    "required": ["reasoning", "vote"],
}

INVESTIGATE = PREFIX + """INSTRUCTIONS:
- It is the Night Phase of Round {{round}}. As {{name}} the {{role}} choose the most suspicious player to investigate.
{% if round == 0 -%}
- There is no information is available in the first round, so choose someone at random.
{% else -%}
- Look for behavior that deviates from typical villager behavior.
- Focus on influential players.
- You must choose someone.
{% endif %}

```json
{
"reasoning": "string", //  Analyze the evidence and justify your decision for who you want to investigate.
"investigate": "string" // Name of the player. Choose from: {{options}}
}
"""

INVESTIGATE_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "investigate": {"type": "string"},
    },
    "required": ["reasoning", "investigate"],
}

ELIMINATE = PREFIX + """INSTRUCTIONS:
- It is the Night Phase of Round {{round}}. As {{name}} the {{role}} choose the most strategic player to remove.
{% if round == 0 -%}
- There is no information is available in the first round, so choose someone at random.
{% else -%}
- Analyze accusations and identify influential Villagers who threaten your anonymity.
- Consider players' behavior and the risks of removing them.
- You must choose someone.
{% endif %}

```json
{
"reasoning": "string", //  Explain your reasoning step-by-step for who you want to remove from the game and why. Avoid using violent or harmful language.
"remove": "string" // Name of the player. Choose from: {{options}}
}
"""

ELIMINATE_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "remove": {"type": "string"},
    },
    "required": ["reasoning", "remove"],
}

PROTECT = PREFIX + """INSTRUCTIONS:
- It is the Night Phase of Round {{round}}. As {{name}} the {{role}} choose the most vulnerable player to protect.
{% if round == 0 -%}
- There is no information is available in the first round, so choose someone at random.
{% else -%}
- Consider who the Werewolves might target.
- Prioritize players with crucial roles like the Seer and yourself.
- You must choose someone.
{% endif %}

```json
{
"reasoning": "string", // Analyze the evidence and justify your decision for who you want to protect.
"protect": "string" // Name of the player. Choose from: {{options}}
}
"""

PROTECT_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "protect": {"type": "string"},
    },
    "required": ["reasoning", "protect"],
}

SUMMARIZE = PREFIX + DEBATE_SO_FAR_THIS_ROUND + """INSTRUCTIONS:
- Reflect on the round's debate as {{name}} the {{role}}.
- Summarize the key points and strategic implications.
{% if role == 'Werewolf' -%}
- Pay attention to accusations against you and your allies.
- Identify sympathetic or easily influenced players.
- Identify key roles for potential elimination.
{% else -%}
- When a player makes a significant statement or shares information, carefully consider its credibility. Does it align with what you already know?
- Analyze how others participate in the debate. Are there any contradictions in their words? Hidden motives behind their actions? Unusually quiet players?
- Based on the debate, can you identify potential allies, trustworthy players, or those who might be the Seer or Doctor?
{% endif %}

```json
{
"reasoning": "string", // Your reasoning about what you should remember from this debate and why this information is important.
"summary": "string" // Summarize the key points and noteworthy observations from the debate in a few sentences. Aim to make notes on as many players as you can — even seemingly insignificant details might become relevant in later rounds. Be specific. Remember, you are {{name}}. Write your summary from their point of view using "I" and "me."
} """

SUMMARIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["reasoning", "summary"],
}

ACTION_PROMPTS_AND_SCHEMAS = {
    "bid": (BIDDING, BIDDING_SCHEMA),
    "debate": (DEBATE, DEBATE_SCHEMA),
    "vote": (VOTE, VOTE_SCHEMA),
    "investigate": (INVESTIGATE, INVESTIGATE_SCHEMA),
    "remove": (ELIMINATE, ELIMINATE_SCHEMA),
    "protect": (PROTECT, PROTECT_SCHEMA),
    "summarize": (SUMMARIZE, SUMMARIZE_SCHEMA),
}