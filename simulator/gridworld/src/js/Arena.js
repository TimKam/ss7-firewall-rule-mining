// import js-son and assign Belief, Plan, Agent, GridWorld, and FieldType to separate consts
import { Belief, Desire, Plan, Agent, GridWorld, FieldType } from 'js-son-agent'

// utils
const genRandomInt = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min
//
window.simulationLog = {
  zones: {},
  clients: {}
}
/* desires, standard agent */
const desires = {
  ...Desire('go', beliefs => {
    if (Math.random() < 0.5) return 'stay'
    const determineDirection = () => {
      const direction = Object.keys(beliefs.neighborStates)[Math.floor(Math.random() * 4)]
      return beliefs.neighborStates[direction] ? direction : determineDirection()
    }
    const direction = determineDirection()
    console.log(direction)
    return direction
  })
}

/* desires, attacker */

const attackerDesires = {
  ...Desire('go', beliefs => {
    const randNumber = Math.random()
    const prePreviousPosition = beliefs.positionLog.length - 3 >= 0
      ? beliefs.positionLog[beliefs.positionLog.length - 3]
      : false
    const previousPosition = beliefs.positionLog.length - 2 >= 0
      ? beliefs.positionLog[beliefs.positionLog.length - 2]
      : false
    const currentPosition = beliefs.positionLog[beliefs.positionLog.length - 1]
    const jumpedLastTurn = previousPosition &&
      prePreviousPosition !== currentPosition &&
      (
        (previousPosition - 1 !== currentPosition && previousPosition % 20 !== 0) ||
        (previousPosition + 1 !== currentPosition && previousPosition % 20 !== 19) ||
        (previousPosition - 20 !== currentPosition) ||
        (previousPosition + 20 !== currentPosition)
      )
    console.log(`jumpedLastTurn: ${jumpedLastTurn}`)
    if (jumpedLastTurn) return 'return'
    if (randNumber < 0.10) return 'jump'
    if (randNumber < 0.60) return 'stay'
    const determineDirection = () => {
      const direction = Object.keys(beliefs.neighborStates)[Math.floor(Math.random() * 4)]
      return beliefs.neighborStates[direction] ? direction : determineDirection()
    }
    const direction = determineDirection()
    console.log(direction)
    return direction
  })
}

const plans = [
  Plan(
    desires => desires.go === 'up',
    () => ({ go: 'up' })
  ),
  Plan(
    desires => desires.go === 'down',
    () => ({ go: 'down' })
  ),
  Plan(
    desires => desires.go === 'left',
    () => ({ go: 'left' })
  ),
  Plan(
    desires => desires.go === 'right',
    () => ({ go: 'right' })
  ),
  Plan(
    desires => desires.go === 'stay',
    () => ({ go: 'stay' })
  ),
  Plan(
    desires => desires.go === 'jump',
    () => ({ go: 'jump' })
  ),
  Plan(
    desires => desires.go === 'return',
    () => ({ go: 'return' })
  )
]

/* helper function to determine the field types of an agent's neighbor fields */
const determineNeighborStates = (position, state) => ({
  down: position + 20 >= 400 ? undefined : state.fields[position + 20],
  up: position - 20 < 0 ? undefined : state.fields[position - 20],
  left: position % 20 === 0 ? undefined : state.fields[position - 1],
  right: position % 20 === 19 ? undefined : state.fields[position + 1]
})

const globalPositionLog = {}
/*
 dynamically generate agents that are aware of their own position and the types of neighboring
 fields
*/
const generateAgents = initialState => initialState.positions.map((position, index) => {
  globalPositionLog[index] = [position]
  const beliefs = {
    ...Belief('neighborStates', determineNeighborStates(position, initialState)),
    ...Belief('position', position),
    ...Belief('positionLog', [position])
  }
  return new Agent(
    index,
    beliefs,
    index === 5 ? attackerDesires : desires,
    plans
  )
})

const determineZone = position => {
  if (position <= 80) return 'zone-1'
  if (position <= 185) return 'zone-2'
  if (position <= 335) return 'zone-3'
  return 'zone-4'
}

/* generate pseudo-random initial state */
const generateInitialState = () => {
  const dimensions = [20, 20]
  const positions = []
  const fields = Array(dimensions[0] * dimensions[1]).fill(0).map((_, index) => {
    const rand = Math.random()
    if (rand < 0.05 && positions.length < 10) {
      window.simulationLog.clients[positions.length] =
      {
        id: positions.length,
        positions: [ determineZone(index) ]
      }
      positions.push(index)
    }
    if (index <= 80) {
      window.simulationLog.zones['zone-1'] =
        {
          id: 'zone-1',
          cells: Array(80 + 1).fill(0).map((_, index) => ({
            x: index % 20,
            y: Math.floor(index / 20)
          }))
        }
      return 'zone-1'
    } else if (index <= 185) {
      window.simulationLog.zones['zone-2'] =
        {
          id: 'zone-2',
          cells: Array(185 - 80).fill(0).map((_, index) => ({
            x: (index + 80) % 20,
            y: Math.floor((index + 80) / 20)
          }))

        }
      return 'zone-2'
    } else if (index <= 335) {
      window.simulationLog.zones['zone-3'] =
        {
          id: 'zone-3',
          cells: Array(335 - 185).fill(0).map((_, index) => ({
            x: (index + 185) % 20,
            y: Math.floor((index + 185) / 20)
          }))

        }
      return 'zone-3'
    } else {
      window.simulationLog.zones['zone-4'] =
        {
          id: 'zone-4',
          cells: Array(400 - 335).fill(0).map((_, index) => ({
            x: (index + 335) % 20,
            y: Math.floor((index + 335) / 20)
          }))

        }
      return 'zone-4'
    }
  })
  return {
    dimensions,
    positions,
    fields
  }
}

const generateConsequence = (state, agentId, newPosition) => {
  switch (state.fields[newPosition]) {
    case 'zone-1':
    case 'zone-2':
    case 'zone-3':
    case 'zone-4':
      if (state.positions.includes(newPosition)) {
        // TODO: remove?
      } else {
        state.positions[agentId] = newPosition
      }
      break
  }
  window.simulationLog.clients[agentId].positions.push(determineZone(state.positions[agentId]))

  return state
}

const trigger = (actions, agentId, state, position) => {
  switch (actions[0].go) {
    case 'down':
      if (position && position + 20 < 400) {
        state = generateConsequence(state, agentId, position + 20)
      }
      break
    case 'up':
      if (position && position - 20 >= 0) {
        state = generateConsequence(state, agentId, position - 20)
      }
      break
    case 'left':
      if (position && position % 20 !== 0) {
        state = generateConsequence(state, agentId, position - 1)
      }
      break
    case 'right':
      if (position && position % 20 !== 19) {
        state = generateConsequence(state, agentId, position + 1)
      }
      break
    case 'stay':
      state = generateConsequence(state, agentId, position)
      break
    case 'jump':
      state = generateConsequence(state, agentId, genRandomInt(0, 399))
      break
    case 'return':
      state = generateConsequence(
        state,
        agentId,
        globalPositionLog[agentId][globalPositionLog[agentId].length - 2]
      )
      break
  }
  return state
}

const stateFilter = (state, agentId, agentBeliefs) => {
  globalPositionLog[agentId].push(state.positions[agentId])
  return {
    ...agentBeliefs,
    positionLog: agentBeliefs.positionLog.concat([state.positions[agentId]]),
    neighborStates: determineNeighborStates(state.positions[agentId], state)
  }
}

const fieldTypes = {
  mountain: FieldType(
    'mountain',
    () => 'mountain-field material-icons mountain',
    () => '^',
    trigger
  ),
  diamond: FieldType(
    'diamond',
    () => 'diamond-field material-icons money',
    () => 'v',
    trigger
  ),
  repair: FieldType(
    'repair',
    () => 'repair-field material-icons build',
    () => 'F',
    trigger
  ),
  plain: FieldType(
    'plain',
    (state, position) => state.positions.includes(position)
      ? 'plain-field material-icons robot'
      : 'plain-field',
    (state, position) => state.positions.includes(position)
      ? 'R'
      : '-',
    trigger,
    (state, position) => state.positions.includes(position)
      ? `<div class="field-annotation">${state.positions.indexOf(position)}</div>`
      : ''
  ),
  'zone-1': FieldType(
    'zone-1',
    (state, position) => state.positions.includes(position)
      ? 'zone-1-field material-icons robot'
      : 'zone-1-field',
    (state, position) => state.positions.includes(position)
      ? 'R'
      : '-',
    trigger,
    (state, position) => state.positions.includes(position)
      ? `<div class="field-annotation">${state.positions.indexOf(position)}</div>`
      : ''
  ),
  'zone-2': FieldType(
    'zone-2',
    (state, position) => state.positions.includes(position)
      ? 'zone-2-field material-icons robot'
      : 'zone-2-field',
    (state, position) => state.positions.includes(position)
      ? 'R'
      : '-',
    trigger,
    (state, position) => state.positions.includes(position)
      ? `<div class="field-annotation">${state.positions.indexOf(position)}</div>`
      : ''
  ),
  'zone-3': FieldType(
    'zone-3',
    (state, position) => state.positions.includes(position)
      ? 'zone-3-field material-icons robot'
      : 'zone-3-field',
    (state, position) => state.positions.includes(position)
      ? 'R'
      : '-',
    trigger,
    (state, position) => state.positions.includes(position)
      ? `<div class="field-annotation">${state.positions.indexOf(position)}</div>`
      : ''
  ),
  'zone-4': FieldType(
    'zone-4',
    (state, position) => state.positions.includes(position)
      ? 'zone-4-field material-icons robot'
      : 'zone-4-field',
    (state, position) => state.positions.includes(position)
      ? 'R'
      : '-',
    trigger,
    (state, position) => state.positions.includes(position)
      ? `<div class="field-annotation">${state.positions.indexOf(position)}</div>`
      : ''
  )
}

const Arena = () => {
  const initialState = generateInitialState()
  return new GridWorld(
    generateAgents(initialState),
    initialState,
    fieldTypes,
    stateFilter
  )
}

export default Arena
