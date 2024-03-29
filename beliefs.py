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
        for j,col in enumerate(k):
            item += "\t" + COLORNAMES[j] + ": " + str(col) + "\n"
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

def format_probs(k):
    result = ""
    for col in ALL_COLORS:
        for i,cnt in enumerate(k[col]):
            if cnt > 0:
                result += COLORNAMES[col] + " " + str(i+1) + ": %.2f\n"%cnt 
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
    total = 1.0*sum(map(sum, knowledge))
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
    
def knormalize(knowledge):
    return map(normalize,  knowledge)
    
def playable_probability(knowledge, board):
    norm = normalize(knowledge)
    prob = 0
    for col in ALL_COLORS:
        if board[col][1] < 5:
            prob += norm[col][board[col][1]]
    return prob
    
def limits(trash):
    result = []
    limit = {col: 6 for col in ALL_COLORS}
    for col in ALL_COLORS:
        for r in range(5):
            if trash.count((col,r+1)) == 2 and limit[col] > r+1:
                limit[col] = r+1
    return limit
    
def useless_probability(knowledge, board, trash):
    norm = normalize(knowledge)
    prob = 0
    lims = limits(trash)
    for col in ALL_COLORS:
        for i in xrange(board[col][1]):
            prob += norm[col][i]
        for i in xrange(lims[col], 6):
            prob += norm[col][i-1]
    return prob
	
def matches_hint((col,rank), hint):
    if hint.type == HINT_NUMBER:
	    return rank == hint.num - 1
    return col == hint.col
    
    
def interpret_hint(old_knowledge, knowledge, played, trash, other_hands, hint, board, quality, use_timing=False):
    explanation = []
    delta = invert(difference(knowledge, old_knowledge))
    newknowledge = update_knowledge(knowledge, played + trash + other_hands)
    explanation.append(["Updated knowledge"] +  map(format_probs, newknowledge))
    explanation.append(["Updated normalized knowledge"] +  map(format_probs, knormalize(newknowledge)))
    
    newknowledge_discard = update_knowledge(knowledge, played + trash + other_hands)
    hasplayable = False
    update = []
    factor = 2.0
    devaluation = 10.0
    discarddevaluation = 2.0
    if use_timing:
        factor *= quality
        devaluation *= quality
        discarddevaluation *= quality
    devaluation = 1/devaluation 
    discarddevaluation = 1/discarddevaluation
    
    explanation.append(["Factors", str(devaluation), str(discarddevaluation), str(factor), str(quality)])
    mods = []
    for d,k,k1 in zip(delta, newknowledge, newknowledge_discard):
        uu = ""
        if potentially_playable(get_possible(delta), board):
            hasplayable = True
            
            for c in ALL_COLORS:
                if board[c][1] < 5 and d[c][board[c][1]] > 0 and matches_hint(board[c], hint):
                    
                    uu += COLORNAMES[c] + " " + str(board[c][1] + 1) + "(%.2f*%.3f)\n"%(k[c][board[c][1]],factor)
                    k[c][board[c][1]] *= factor
                for i in xrange(5):
                    if i != board[c][1] or not matches_hint(board[c], hint):
                        uu += COLORNAMES[c] + " " + str(i + 1) + "(%.2f*%.3f)\n"%(k[c][i],devaluation)
                        k[c][i] *= devaluation
                        
        update.append(uu)
        if potentially_useless(get_possible(delta), board):
            for c in ALL_COLORS:
                for i in xrange(5):
                    if i < board[c][1]:
                        k1[c][i] *= factor
                    elif i >= board[c][1]:
                        k1[c][i] *= discarddevaluation
   
    explanation.append(["Information delta from hint"] + map(format_knowledge, delta))
    explanation.append(["Probability update"] + update)
    explanation.append(["Card probabilities"] +  map(format_probs, knormalize(newknowledge)))
    currbest = 0.875
    
    delta = 1-currbest
    pp = None
    if hasplayable:
        play = None
        ppbs = []
        for i,c in enumerate(newknowledge):
            playprob = playable_probability(c, board)
            ppbs.append("%.2f"%playprob)
            if playprob > currbest - delta:
                pp = c
                play = i 
                currbest = playprob
                delta = (1-currbest)/2
        explanation.append(["Playability probabilities"] + ppbs)
        if play is not None:
            #print fk(newknowledge)
            return (Action(PLAY, cnr=play, comment="PLAYPROB: $player %.2f %.2f"%(currbest, quality)), True, explanation)
    
    discard = None
    discprob = 0
    for i,c in enumerate(newknowledge_discard):
        playprob = useless_probability(c, board, trash)
        if playprob > 0.7:
            discard = i 
            discprob = playprob
    #if discard is not None:
    #    return (Action(DISCARD, cnr=discard, comment="DISCPROB: $player %.2f %.2f"%(discprob, quality)), True, explanation)
    
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
    return (Action(DISCARD, cnr=besti), False, explanation)
    
    
    