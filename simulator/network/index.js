// URL for config state management
const url = new URL(window.location.href)

const nodParam = url.searchParams.get('nod')
const aggParam = url.searchParams.get('agg')
const fixParam = url.searchParams.get('fix')
const speParam = url.searchParams.get('spe')
const attParam = url.searchParams.get('att')
const mulRunParam = url.searchParams.get('mul')

// configuration settings
const numberOfNodes = nodParam ? Number(nodParam) : 40
const hubFixation = fixParam ? Number(fixParam) / 100 : 0.5
const aggressionLevel = aggParam ? Number(aggParam) / 100 : 0.5
const numberOfHubs = 3
const speed = speParam ? 2500 / Number(speParam) : 500
const attackFromHub = attParam === 'true'
const multipleRuns = mulRunParam === 'true'
let showAttacker = false

// "file global" object to manage graph library, edges, nodes, hubs, and attackers
let cy
let edges
let nodes 
let hubs
let noHubNodes
let attacker
let globalDistances = [...Array(numberOfNodes)]
const networkHistory = []
const ticksLimit = 500
const notificationLimit = 50000
let ticksCounter = 0

// utils
const genRandomInt = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min

// initialization function
const init = () => {
    cy, edges, nodes, hubs, noHubNodes, attacker = null
    globalDistances = [...Array(numberOfNodes)]
    ticksCounter = 0
    // assign random hubs
    hubs = Array.from(Array(numberOfHubs)).map(
        (_, __) => Math.floor(Math.random() * numberOfNodes)
    )
    // set attacker
    if (!attacker) { // determine attacker if this has not been done, yet
        // if attacker should be hub
        if (attackFromHub) {
            attacker = hubs[genRandomInt(0, hubs.length - 1)]
        } else { // if attacker should not be hub
            potentialNodes = [...Array(numberOfNodes).keys()]
            noHubNodes = potentialNodes.filter(id => !hubs.includes(id))
            attacker = noHubNodes[genRandomInt(0, noHubNodes.length - 1)]
        }
        hubs.forEach(hubId => cy.$id(hubId).style({'background-color': '#73A790'}))
        document.getElementById('show-button').classList.remove('disabled')
    }
}

// edge creation functions (helpers)
const genRandomTarget = source => {
    const target = genRandomInt(0, numberOfNodes - 1)
    return target == source ? genRandomTarget(source) : target
}

const genRandomConnection = () => {
    const source = genRandomInt(0, numberOfNodes - 1)
    const target = genRandomTarget(source)
    return source == target ? genRandomConnection() : { source, target }
}

// get ln "random" node based on distance
const getLnRandomNode = (nodeIds, source) => {
    let sortedDistances
    if(!globalDistances[source] || globalDistances[source].length === numberOfHubs) {
        const distances = nodeIds.map((id, index) => {
            const node = nodes[id]
            const a = node.position.x - nodes[source].position.x
            const b = node.position.y - nodes[source].position.y
            return {
                id: id,
                distance: Math.sqrt( a*a + b*b )
            }
        })
        sortedDistances = distances.sort((a, b) => a.distance > b.distance)
        globalDistances[source] = sortedDistances
    } else {
        sortedDistances = globalDistances[source]
    }
    let index = Math.ceil(jStat.lognormal.sample(1, 0.5) * 0.75) - 1
    let id
    //const
    if (index >= sortedDistances.length) {
        const limit = sortedDistances.length - 1 < 5 ? sortedDistances.length - 1 : 5
        index = genRandomInt(0, limit)
    }
    id = sortedDistances[index].id
    if (id === source) {
        sortedDistances[1].id
    }
    return id
}

const genGraphBasedConnection = (source, target) => {
    if(source === attacker && Math.random() < aggressionLevel) {
        target = genRandomTarget(source)
        return { source, target }
    }
    if(Math.random() < hubFixation) { // pick random Hub as source
        source = hubs[genRandomInt(0, hubs.length - 1)]
    }
   if(Math.random() < hubFixation) { // pick "random" Hub as target, biased based on distance
        target = getLnRandomNode(hubs, source)
    } else { // pick "random" non-Hub as target, biased based on distance
        target = getLnRandomNode(noHubNodes, source)
    }
    if(source == target) {
        return genGraphBasedConnection(hubs[0], hubs[1])
    }
    return { source, target }
}

// core logic
const startSimulation = () => {
    if(cy)  {
        cy.unmount()
        cy.destroy()
    }
    const initCy = () => {
        edges = {}
        hubs = []
    
        nodes = new Array(numberOfNodes).fill({}).map((_, index) => {
            return {
                group: 'nodes',
                data: { id: index },
                grabbable: false
            }
        })
    }

    initCy()

    const render = elements => cytoscape({
        container: document.getElementById('cy'),
        elements,
        style: [
        {
            selector: 'node',
            style: {
            'background-color': '#666',
            // 'label': 'data(id)'
            }
        },
    
        {
            selector: 'edge',
            style: {
            'width': 3,
            'line-color': '#ccc',
            'target-arrow-color': '#ccc',
            'target-arrow-shape': 'triangle'
            }
        }
        ],
    })

    cy = render(nodes)
    const layout = cy.layout({name: 'random'})
    layout.run()
    nodes.forEach((node, index) => nodes[index] = {
        ...node,
        position: cy.$id(node.data.id).position()
        }
    )
    cy.zoomingEnabled(false)

    cy.ready(() => {
        init()
        const interval = setInterval(() => {
            if(multipleRuns && ticksCounter === ticksLimit) {
                clearInterval(interval)
                startSimulation()
            }
            if(networkHistory.length === notificationLimit) {
                alert(`Reached ${notificationLimit} ticks`)
            }
            ticksCounter++
            let connection = genRandomConnection()
            const source = connection.source
            const target = connection.target
            const edgeArray = Object.values(edges)
            const existingEdge = edgeArray.find(edge => {
                return (edge.data.source == source && edge.data.target == target) ||
                    (edge.data.target == source && edge.data.source == target)
                }
            )
            const edgeId = numberOfNodes + edgeArray.length
            if (existingEdge) {
                const edgeUpdate = {
                    ...existingEdge,
                    style: { width: existingEdge.style.width + 0.1 }
                }
                edges[existingEdge.data.id] = edgeUpdate
                cy.$id(existingEdge.data.id).style('width', edgeUpdate.style.width)
            } else {
                const finalConnection = genGraphBasedConnection(source, target)
                const edge = {
                    data: {
                        id: edgeId,
                        source: finalConnection.source,
                        target: finalConnection.target
                    },
                    style: { width: 0.1 }
                }
                edges[edgeId] = edge
                cy.add([edge])
            }
            const historyEntry = { edges, nodes }
            networkHistory.push(historyEntry)
            /*if (ticksCounter % 50 === 0) {
                const uriContent = `data:text/plain;charset=utf-8,${encodeURIComponent(JSON.stringify(networkHistory))}`
                document.getElementById('log-button').href = uriContent
            }*/
        }, speed)
    })
}

window.addEventListener('DOMContentLoaded', _ => {
    document.getElementById('restart-button').onclick = () => location.reload()
    const showButton = document.getElementById('show-button')
    showButton.onclick = () => {
        if (showAttacker) {
            cy.$id(attacker).style({'background-color': '#F0EEE3'})
            showButton.text = "Show Attacker"
        } else {
            cy.$id(attacker).style({'background-color': '#D7B17C'})
            showButton.text = "Hide Attacker"
        }
        showAttacker = !showAttacker
    }
    window.setTimeout(() => startSimulation(), 500)
    
})

function updateConfig (id, value) {
    try {
        const label = document.getElementById(`${id.substring(0,3)}-tracker`)
        const previousLabelText = label.value
        label.value = `${previousLabelText.split(':')[0]}: ${value}`
    } catch  (error) {}
    url.searchParams.set(id.substring(0,3), value)
    window.history.pushState({ path: url.href }, '', url.href)
}
