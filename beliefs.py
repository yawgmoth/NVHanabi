import copy

from actions import *

COUNTS = [3,2,2,2,1]

HINT_VALUE = 0.5

def fk1(knowledge):
    item = ""
    for i,col in enumerate(knowledge):
        item += "%s: "%(COLORNAMES[i]) + str(col) + "\n"
    return item

def fk(knowledge):
    result = ""
    for i,k in enumerate(knowledge):
        item = ""
        for col in k:
            item += "\t" + str(col) + "\n"
        result += "card %d\n%s"%(i,item)
    return result
          
def initial_knowledge(n=0):
    if n > 0:
        return [initial_knowledge() for i in xrange(n)]
    knowledge = []
    for col in ALL_COLORS:
        knowledge.append(COUNTS[:])
    return knowledge
    
def hint_color(knowledge, color, truth):
    result = []
    for col in ALL_COLORS:
        if truth == (col == color):
            result.append(knowledge[col][:])
        else:
            result.append([0 for i in knowledge[col]])
    return result
    
def hint_rank(knowledge, rank, truth):
    result = []
    for col in ALL_COLORS:
        colknow = []
        for i,k in enumerate(knowledge[col]):
            if truth == (i + 1 == rank):
                colknow.append(k)
            else:
                colknow.append(0)
        result.append(colknow)
    return result
    
def iscard((c,n)):
    knowledge = []
    for col in ALL_COLORS:
        knowledge.append(COUNTS[:])
        for i in xrange(len(knowledge[-1])):
            if col != c or i+1 != n:
                knowledge[-1][i] = 0
            else:
                knowledge[-1][i] = 1
            
    return knowledge
    
def format_knowledge(k):
    result = ""
    for col in ALL_COLORS:
        for i,cnt in enumerate(k[col]):
            if cnt > 0:
                result += COLORNAMES[col] + " " + str(i+1) + ": " + str(cnt) + "\n"
    return result

def get_possible(knowledge):
    result = []
    for col in ALL_COLORS:
        for i,cnt in enumerate(knowledge[col]):
            if cnt > 0:
                result.append((col,i+1))
    return result
    
def playable(possible, board):
    for (col,nr) in possible:
        if board[col][1] + 1 != nr:
            return False
    return True
    
def potentially_playable(possible, board):
    for (col,nr) in possible:
        if board[col][1] + 1 == nr:
            return True
    return False
    
def discardable(possible, board):
    for (col,nr) in possible:
        if board[col][1] < nr:
            return False
    return True
    
def potentially_useless(possible, board):
    for (col,nr) in possible:
        if board[col][1] >= nr:
            return True
    return False
    
def update_knowledge(knowledge, used):
    result = copy.deepcopy(knowledge)
    for r in result:
        for (c,nr) in used:
            r[c][nr-1] = max(r[c][nr-1] - 1, 0)
    return result    

def probabilities(knowledge, board, trash, other_hands):
    which = update_knowledge(knowledge, board + trash + other_hands)
    for i in xrange(len(which)):
        possibilities = sum(map(sum, which[i]))
        for col in ALL_COLORS:
            for rank in range(5):
                which[i][col][rank] = which[i][col][rank]*1.0/possibilities
    return which
    
def difference(a, b):
    result = []
    for c in zip(a,b):
        cardinfo = []
        for col in ALL_COLORS:
            tmp = []
            for rank in range(5):
                tmp.append(c[1][col][rank] - c[0][col][rank])
            cardinfo.append(tmp)
        result.append(cardinfo)
    return result
    
def invert(k):
    return difference(k, initial_knowledge(len(k)))
    
def normalize(knowledge):
    total = sum(map(sum, knowledge))
    result = []
    for col in ALL_COLORS:
        colk = []
        for r in xrange(5):
            if total:
                colk.append(knowledge[col][r]/total)
            else: 
                colk.append(0)
        result.append(colk)
    return result
    
def playable_probability(knowledge, board):
    norm = normalize(knowledge)
    prob = 0
    for col in ALL_COLORS:
        if board[col][1] < 5:
            prob += norm[col][board[col][1]]
    return prob
    
def useless_probability(knowledge, board):
    norm = normalize(knowledge)
    prob = 0
    for col in ALL_COLORS:
        for i in xrange(board[col][1]):
            prob += norm[col][i]
    return prob
    
    
def interpret_hint(old_knowledge, knowledge, played, trash, other_hands, hint, board):
    
    delta = invert(difference(knowledge, old_knowledge))
    
    newknowledge = update_knowledge(knowledge, board + trash + other_hands)
    newknowledge_discard = update_knowledge(knowledge, board + trash + other_hands)
    hasplayable = False
    for d,k,k1 in zip(delta, newknowledge, newknowledge_discard):
        if potentially_playable(get_possible(delta), board):
            hasplayable = True
            for c in ALL_COLORS:
                if board[c][1] < 5 and d[c][board[c][1]] > 0:
                    k[c][board[c][1]] *= 2
                for i in xrange(5):
                    if i != board[c][1]:
                        k[c][i] *= 0.1
        if potentially_useless(get_possible(delta), board):
            for c in ALL_COLORS:
                for i in xrange(5):
                    if i < board[c][1]:
                        k[c][i] *= 2
                    elif i >= board[c][1]:
                        k[c][i] *= 0.5
    if hasplayable:
        play = None
        for i,c in enumerate(newknowledge):
            playprob = playable_probability(c, board)
            if playprob > 0.85:
                play = i 
        if play is not None:
            return (Action(PLAY, cnr=play), True)
 
    discard = None
    for i,c in enumerate(newknowledge_discard):
        playprob = useless_probability(c, board)
        if playprob > 0.85:
            discard = i 
    if discard is not None:
        return (Action(DISCARD, cnr=discard), True)
    
    newknowledge = update_knowledge(knowledge, board + trash + other_hands)
    probs = map(normalize, newknowledge)
    best = -10000
    besti = None
    for cnr, (cprobs, cknow) in enumerate(zip(probs, newknowledge)):
        expected = 0
        for col in ALL_COLORS:
            for i,prob in enumerate(cprobs[col]):
                rank = i+1
                if prob > 0.001:
                    if board[col][1] >= rank:
                        expected += prob*HINT_VALUE
                    else:
                        dist = rank - board[col][1]
                        if cknow[col][i] > 1:
                            value = prob*(6-rank)/(dist*dist)
                        else:
                            value = (6-rank)
                        if rank == 5:
                            value += HINT_VALUE
                        value *= prob
                        expected -= value
        if expected > best:
            besti = cnr
    return (Action(DISCARD, cnr=besti), False)
    
    
    