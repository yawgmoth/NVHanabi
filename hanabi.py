import random
import sys
import copy
import time
from beliefs import *
from actions import *
import argparse



# semi-intelligently format cards in any format
def f(something):
    if type(something) == list:
        return map(f, something)
    elif type(something) == dict:
        return {k: something(v) for (k,v) in something.iteritems()}
    elif type(something) == tuple and len(something) == 2:
        return (COLORNAMES[something[0]],something[1])
    return something

def make_deck():
    deck = []
    for col in ALL_COLORS:
        for num, cnt in enumerate(COUNTS):
            for i in xrange(cnt):
                deck.append((col, num+1))
    random.shuffle(deck)
    return deck

        
class Player(object):
    def __init__(self, name, pnr):
        self.name = name
        self.explanation = []
    def get_action(self, nr, hands, knowledge, trash, played, board, valid_actions, hints):
        return random.choice(valid_actions)
    def inform(self, action, player, game):
        pass
    def get_explanation(self):
        return self.explanation

a = 1   

CANDISCARD = 128

def format_intention(i):
    if isinstance(i, str):
        return i
    if i == PLAY:
        return "Play"
    elif i == DISCARD:
        return "Discard"
    elif i == CANDISCARD:
        return "Can Discard"
    return "Keep"
    
def whattodo(knowledge, pointed, board):
    possible = get_possible(knowledge)
    play = potentially_playable(possible, board)
    discard = potentially_useless(possible, board)
    
    if play and pointed:
        return PLAY
    if discard and pointed:
        return DISCARD
    return None

def pretend(action, knowledge, intentions, hand, board):
    (type,value) = action
    positive = []
    haspositive = False
    change = False
    if type == HINT_COLOR:
        newknowledge = []
        for i,(col,num) in enumerate(hand):
            positive.append(value==col)
            newknowledge.append(hint_color(knowledge[i], value, value == col))
            if value == col:
                haspositive = True
                if newknowledge[-1] != knowledge[i]:
                    change = True
    else:
        newknowledge = []
        for i,(col,num) in enumerate(hand):
            positive.append(value==num)
            
            newknowledge.append(hint_rank(knowledge[i], value, value == num))
            if value == num:
                haspositive = True
                if newknowledge[-1] != knowledge[i]:
                    change = True
    if not haspositive:
        return False, 0, ["Invalid hint"]
    if not change:
        return False, 0, ["No new information"]
    score = 0
    predictions = []
    pos = False
    for i,c,k,p in zip(intentions, hand, newknowledge, positive):
        
        action = whattodo(k, p, board)
        
        if action == PLAY and i != PLAY:
            #print "would cause them to play", f(c)
            return False, 0, predictions + [PLAY]
        
        if action == DISCARD and i not in [DISCARD, CANDISCARD]:
            #print "would cause them to discard", f(c)
            return False, 0, predictions + [DISCARD]
            
        if action == PLAY and i == PLAY:
            pos = True
            predictions.append(PLAY)
            score += 3
        elif action == DISCARD and i in [DISCARD, CANDISCARD]:
            pos = True
            predictions.append(DISCARD)
            if i == DISCARD:
                score += 2
            else:
                score += 1
        else:
            predictions.append(None)
    if not pos:
        return False, score, predictions
    return True,score, predictions
    

    
def pretend_discard(act, knowledge, board, trash):
    which = copy.deepcopy(knowledge[act.cnr])
    for (col,num) in trash:
        if which[col][num-1]:
            which[col][num-1] -= 1
    for col in ALL_COLORS:
        for i in xrange(board[col][1]):
            if which[col][i]:
                which[col][i] -= 1
    possibilities = sum(map(sum, which))
    expected = 0
    terms = []
    for col in ALL_COLORS:
        for i,cnt in enumerate(which[col]):
            rank = i+1
            if cnt > 0:
                prob = cnt*1.0/possibilities
                if board[col][1] >= rank:
                    expected += prob*HINT_VALUE
                    terms.append((col,rank,cnt,prob,prob*HINT_VALUE))
                else:
                    dist = rank - board[col][1]
                    if cnt > 1:
                        value = prob*(6-rank)/(dist*dist)
                    else:
                        value = (6-rank)
                    if rank == 5:
                        value += HINT_VALUE
                    value *= prob
                    expected -= value
                    terms.append((col,rank,cnt,prob,-value))
    return (act, expected, terms)
    
used = {}
for c in ALL_COLORS:
    for i,cnt in enumerate(COUNTS):
        used[(c,i+1)] = 0
        
class SelfIntentionalPlayer(Player):
    def __init__(self, name, pnr):
        self.name = name
        self.hints = {}
        self.pnr = pnr
        self.gothint = None
        self.last_knowledge = []
        self.last_played = []
        self.last_board = []
        self.explanation = []
    def get_action(self, nr, hands, knowledge, trash, played, board, valid_actions, hints):
        handsize = len(knowledge[0])
        possible = []
        result = None
        self.explanation = []
        self.explanation.append(["Your Hand:"] + map(f, hands[1-nr]))
        action = []
        if self.gothint:
            (act,plr) = self.gothint
            if act.type == HINT_COLOR:
                for k in knowledge[nr]:
                    action.append(whattodo(k, sum(k[act.col]) > 0, board))
            elif act.type == HINT_NUMBER:
                for k in knowledge[nr]:
                    cnt = 0
                    for c in ALL_COLORS:
                        cnt += k[c][act.num-1]
                    action.append(whattodo(k, cnt > 0, board))
                    

        if action:
            self.explanation.append(["What you want me to do"] + map(format_intention, action))
            for i,a in enumerate(action):
                if a == PLAY and (not result or result.type == DISCARD):
                    result = Action(PLAY, cnr=i)
                elif a == DISCARD and not result:
                    result = Action(DISCARD, cnr=i)

        self.gothint = None
        for k in knowledge[nr]:
            possible.append(get_possible(k))
        
        discards = []
        duplicates = []
        for i,p in enumerate(possible):
            if playable(p,board) and not result:
                result = Action(PLAY, cnr=i)
            if discardable(p,board):
                discards.append(i)

        if discards and hints < 8 and not result:
            result =  Action(DISCARD, cnr=random.choice(discards))
            
        playables = []
        useless = []
        discardables = []
        othercards = trash + board
        intentions = [None for i in xrange(handsize)]
        for i,h in enumerate(hands):
            if i != nr:
                for j,(col,n) in enumerate(h):
                    if board[col][1] + 1 == n:
                        playables.append((i,j))
                        intentions[j] = PLAY
                    if board[col][1] >= n:
                        useless.append((i,j))
                        if not intentions[j]:
                            intentions[j] = DISCARD
                    if n < 5 and (col,n) not in othercards:
                        discardables.append((i,j))
                        if not intentions[j]:
                            intentions[j] = CANDISCARD
        
        self.explanation.append(["Intentions"] + map(format_intention, intentions))
        
        
            
        if hints > 0:
            valid = []
            for c in ALL_COLORS:
                action = (HINT_COLOR, c)
                #print "HINT", COLORNAMES[c],
                (isvalid,score,expl) = pretend(action, knowledge[1-nr], intentions, hands[1-nr], board)
                self.explanation.append(["Prediction for: Hint Color " + COLORNAMES[c]] + map(format_intention, expl))
                #print isvalid, score
                if isvalid:
                    valid.append((action,score))
            
            for r in xrange(5):
                r += 1
                action = (HINT_NUMBER, r)
                #print "HINT", r,
                
                (isvalid,score, expl) = pretend(action, knowledge[1-nr], intentions, hands[1-nr], board)
                self.explanation.append(["Prediction for: Hint Rank " + str(r)] + map(format_intention, expl))
                #print isvalid, score
                if isvalid:
                    valid.append((action,score))
                 
            if valid and not result:
                valid.sort(key=lambda (a,s): -s)
                #print valid
                (a,s) = valid[0]
                if a[0] == HINT_COLOR:
                    result = Action(HINT_COLOR, pnr=1-nr, col=a[1])
                else:
                    result = Action(HINT_NUMBER, pnr=1-nr, num=a[1])

        self.explanation.append(["My Knowledge"] + map(format_knowledge, knowledge[nr]))
        possible = [ Action(DISCARD, cnr=i) for i in xrange(handsize) ]
        
        scores = map(lambda p: pretend_discard(p, knowledge[nr], board, trash), possible)
        def format_term((col,rank,n,prob,val)):
            return COLORNAMES[col] + " " + str(rank) + " (%.2f%%): %.2f"%(prob*100, val)
            
        self.explanation.append(["Discard Scores"] + map(lambda (a,s,t): "\n".join(map(format_term, t)) + "\n%.2f"%(s), scores))
        scores.sort(key=lambda (a,s,t): -s)
        if result:
            return result
        return scores[0][0]
        
        return random.choice([Action(DISCARD, cnr=i) for i in xrange(handsize)])
    def inform(self, action, player, game):
        if action.type in [PLAY, DISCARD]:
            x = str(action)
            if (action.cnr,player) in self.hints:
                self.hints[(action.cnr,player)] = []
            for i in xrange(10):
                if (action.cnr+i+1,player) in self.hints:
                    self.hints[(action.cnr+i,player)] = self.hints[(action.cnr+i+1,player)]
                    self.hints[(action.cnr+i+1,player)] = []
        elif action.pnr == self.pnr:
            self.gothint = (action,player)
            self.last_knowledge = game.knowledge[:]
            self.last_board = game.board[:]
            self.last_trash = game.trash[:]
            self.played = game.played[:]
            
class ProbablyIntentionalPlayer(Player):
    def __init__(self, name, pnr):
        self.name = name
        self.hints = {}
        self.pnr = pnr
        self.gothint = None
        self.last_knowledge = []
        self.last_played = []
        self.last_board = []
        self.explanation = []
    def get_action(self, nr, hands, knowledge, trash, played, board, valid_actions, hints):
        if not self.last_knowledge:
            self.last_knowledge = [initial_knowledge(len(knowledge[nr])) for i in knowledge]
        probs = probabilities(knowledge[nr], played, trash, hands[1-nr])
        
        handsize = len(knowledge[0])
        
        possible = []
        result = None
        self.explanation = []
        self.explanation.append(["Your Hand:"] + map(f, hands[1-nr]))
        action = []
        iact = None
        if self.gothint:
            (act,plr) = self.gothint
            (iact,force) = interpret_hint(self.last_knowledge[nr], knowledge[nr], played, trash, hands[1-nr], act, board)
            if force: 
                return iact


        if action:
            self.explanation.append(["What you want me to do"] + map(format_intention, action))
            for i,a in enumerate(action):
                if a == PLAY and (not result or result.type == DISCARD):
                    result = Action(PLAY, cnr=i)
                elif a == DISCARD and not result:
                    result = Action(DISCARD, cnr=i)

        self.gothint = None
        for k in knowledge[nr]:
            possible.append(get_possible(k))
        
        discards = []
        duplicates = []
        for i,p in enumerate(possible):
            if playable(p,board) and not result:
                result = Action(PLAY, cnr=i)
            if discardable(p,board):
                discards.append(i)

        if discards and hints < 8 and not result:
            result =  Action(DISCARD, cnr=random.choice(discards))
            
        playables = []
        useless = []
        discardables = []
        othercards = trash + board
        intentions = [None for i in xrange(handsize)]
        for i,h in enumerate(hands):
            if i != nr:
                for j,(col,n) in enumerate(h):
                    if board[col][1] + 1 == n:
                        playables.append((i,j))
                        intentions[j] = PLAY
                    if board[col][1] >= n:
                        useless.append((i,j))
                        if not intentions[j]:
                            intentions[j] = DISCARD
                    if n < 5 and (col,n) not in othercards:
                        discardables.append((i,j))
                        if not intentions[j]:
                            intentions[j] = CANDISCARD
        
        self.explanation.append(["Intentions"] + map(format_intention, intentions))
        
        
            
        if hints > 0:
            valid = []
            for c in ALL_COLORS:
                action = (HINT_COLOR, c)
                #print "HINT", COLORNAMES[c],
                (isvalid,score,expl) = pretend(action, knowledge[1-nr], intentions, hands[1-nr], board)
                self.explanation.append(["Prediction for: Hint Color " + COLORNAMES[c]] + map(format_intention, expl))
                #print isvalid, score
                if isvalid:
                    valid.append((action,score))
            
            for r in xrange(5):
                r += 1
                action = (HINT_NUMBER, r)
                #print "HINT", r,
                
                (isvalid,score, expl) = pretend(action, knowledge[1-nr], intentions, hands[1-nr], board)
                self.explanation.append(["Prediction for: Hint Rank " + str(r)] + map(format_intention, expl))
                #print isvalid, score
                if isvalid:
                    valid.append((action,score))
                 
            if valid and not result:
                valid.sort(key=lambda (a,s): -s)
                #print valid
                (a,s) = valid[0]
                if a[0] == HINT_COLOR:
                    result = Action(HINT_COLOR, pnr=1-nr, col=a[1])
                else:
                    result = Action(HINT_NUMBER, pnr=1-nr, num=a[1])

        self.explanation.append(["My Knowledge"] + map(format_knowledge, knowledge[nr]))
        possible = [ Action(DISCARD, cnr=i) for i in xrange(handsize) ]
        
        scores = map(lambda p: pretend_discard(p, knowledge[nr], board, trash), possible)
        def format_term((col,rank,n,prob,val)):
            return COLORNAMES[col] + " " + str(rank) + " (%.2f%%): %.2f"%(prob*100, val)
            
        self.explanation.append(["Discard Scores"] + map(lambda (a,s,t): "\n".join(map(format_term, t)) + "\n%.2f"%(s), scores))
        scores.sort(key=lambda (a,s,t): -s)
        self.last_knowledge = copy.deepcopy(knowledge)
        if result:
            return result
        if iact:
            return iact
        return scores[0][0]
        
        return random.choice([Action(DISCARD, cnr=i) for i in xrange(handsize)])
    def inform(self, action, player, game):
        if action.type in [PLAY, DISCARD]:
            x = str(action)
            if (action.cnr,player) in self.hints:
                self.hints[(action.cnr,player)] = []
            for i in xrange(10):
                if (action.cnr+i+1,player) in self.hints:
                    self.hints[(action.cnr+i,player)] = self.hints[(action.cnr+i+1,player)]
                    self.hints[(action.cnr+i+1,player)] = []
        elif action.pnr == self.pnr:
            self.gothint = (action,player)
            self.last_board = game.board[:]
            self.last_trash = game.trash[:]
            self.played = game.played[:]
        
def format_card((col,num)):
    return COLORNAMES[col] + " " + str(num)
        
def format_hand(hand):
    return ", ".join(map(format_card, hand))
        

class Game(object):
    def __init__(self, players, log=sys.stdout, format=0):
        self.players = players
        self.hits = 3
        self.hints = 8
        self.current_player = 0
        self.board = map(lambda c: (c,0), ALL_COLORS)
        self.played = []
        self.deck = make_deck()
        self.extra_turns = 0
        self.hands = []
        self.knowledge = []
        self.make_hands()
        self.trash = []
        self.log = log
        self.turn = 1
        self.format = format
        self.dopostsurvey = False
        self.study = False
        if self.format:
            print >> self.log, self.deck
    def make_hands(self):
        handsize = 4
        if len(self.players) < 4:
            handsize = 5
        for i, p in enumerate(self.players):
            self.hands.append([])
            self.knowledge.append([])
            for j in xrange(handsize):
                self.draw_card(i)
    def draw_card(self, pnr=None):
        if pnr is None:
            pnr = self.current_player
        if not self.deck:
            return
        self.hands[pnr].append(self.deck[0])
        self.knowledge[pnr].append(initial_knowledge())
        del self.deck[0]
    def perform(self, action):
        for p in self.players:
            p.inform(action, self.current_player, self)
        if format:
            print >> self.log, "MOVE:", self.current_player, action.type, action.cnr, action.pnr, action.col, action.num
        if action.type == HINT_COLOR:
            self.hints -= 1
            print >>self.log, self.players[self.current_player].name, "hints", self.players[action.pnr].name, "about all their", COLORNAMES[action.col], "cards", "hints remaining:", self.hints
            print >>self.log, self.players[action.pnr].name, "has", format_hand(self.hands[action.pnr])
            for (col,num),knowledge in zip(self.hands[action.pnr],self.knowledge[action.pnr]):
                if col == action.col:
                    for i, k in enumerate(knowledge):
                        if i != col:
                            for i in xrange(len(k)):
                                k[i] = 0
                else:
                    for i in xrange(len(knowledge[action.col])):
                        knowledge[action.col][i] = 0
        elif action.type == HINT_NUMBER:
            self.hints -= 1
            print >>self.log, self.players[self.current_player].name, "hints", self.players[action.pnr].name, "about all their", action.num, "hints remaining:", self.hints
            print >>self.log, self.players[action.pnr].name, "has", format_hand(self.hands[action.pnr])
            for (col,num),knowledge in zip(self.hands[action.pnr],self.knowledge[action.pnr]):
                if num == action.num:
                    for k in knowledge:
                        for i in xrange(len(COUNTS)):
                            if i+1 != num:
                                k[i] = 0
                else:
                    for k in knowledge:
                        k[action.num-1] = 0
        elif action.type == PLAY:
            (col,num) = self.hands[self.current_player][action.cnr]
            print >>self.log, self.players[self.current_player].name, "plays", format_card((col,num)),
            if self.board[col][1] == num-1:
                self.board[col] = (col,num)
                self.played.append((col,num))
                if num == 5:
                    self.hints += 1
                    self.hints = min(self.hints, 8)
                print >>self.log, "successfully! Board is now", format_hand(self.board)
            else:
                self.trash.append((col,num))
                self.hits -= 1
                print >>self.log, "and fails. Board was", format_hand(self.board)
            del self.hands[self.current_player][action.cnr]
            del self.knowledge[self.current_player][action.cnr]
            self.draw_card()
            print >>self.log, self.players[self.current_player].name, "now has", format_hand(self.hands[self.current_player])
        else:
            self.hints += 1 
            self.hints = min(self.hints, 8)
            self.trash.append(self.hands[self.current_player][action.cnr])
            print >>self.log, self.players[self.current_player].name, "discards", format_card(self.hands[self.current_player][action.cnr])
            print >>self.log, "trash is now", format_hand(self.trash)
            del self.hands[self.current_player][action.cnr]
            del self.knowledge[self.current_player][action.cnr]
            self.draw_card()
            print >>self.log, self.players[self.current_player].name, "now has", format_hand(self.hands[self.current_player])
    def valid_actions(self):
        valid = []
        for i in xrange(len(self.hands[self.current_player])):
            valid.append(Action(PLAY, cnr=i))
            valid.append(Action(DISCARD, cnr=i))
        if self.hints > 0:
            for i, p in enumerate(self.players):
                if i != self.current_player:
                    for col in set(map(lambda (col,num): col, self.hands[i])):
                        valid.append(Action(HINT_COLOR, pnr=i, col=col))
                    for num in set(map(lambda (col,num): num, self.hands[i])):
                        valid.append(Action(HINT_NUMBER, pnr=i, num=num))
        return valid
    def run(self, turns=-1):
        self.turn = 1
        while not self.done() and (turns < 0 or self.turn < turns):
            self.turn += 1
            if not self.deck:
                self.extra_turns += 1
            hands = []
            for i, h in enumerate(self.hands):
                if i == self.current_player:
                    hands.append([])
                else:
                    hands.append(h)
            action = self.players[self.current_player].get_action(self.current_player, hands, self.knowledge, self.trash, self.played, self.board, self.valid_actions(), self.hints)
            self.perform(action)
            self.current_player += 1
            self.current_player %= len(self.players)
        print >>self.log, "Game done, hits left:", self.hits
        points = self.score()
        print >>self.log, "Points:", points
        return points
    def score(self):
        return sum(map(lambda (col,num): num, self.board))
    def single_turn(self):
        if not self.done():
            if not self.deck:
                self.extra_turns += 1
            hands = []
            for i, h in enumerate(self.hands):
                if i == self.current_player:
                    hands.append([])
                else:
                    hands.append(h)
            action = self.players[self.current_player].get_action(self.current_player, hands, self.knowledge, self.trash, self.played, self.board, self.valid_actions(), self.hints)
            self.perform(action)
            self.current_player += 1
            self.current_player %= len(self.players)
    def external_turn(self, action): 
        if not self.done():
            if not self.deck:
                self.extra_turns += 1
            self.perform(action)
            self.current_player += 1
            self.current_player %= len(self.players)
    def done(self):
        if self.extra_turns == len(self.players) or self.hits == 0:
            return True
        for (col,num) in self.board:
            if num != 5:
                return False
        return True
    def finish(self):
        if self.format:
            print >> self.log, "Score", self.score()
            self.log.close()
        
    
class NullStream(object):
    def write(self, *args):
        pass
        
random.seed(123)

playertypes = {"random": Player, "full": SelfIntentionalPlayer, "prob": ProbablyIntentionalPlayer}
names = ["Shangdi", "Yu Di", "Tian", "Nu Wa", "Pangu"]
        
        
def make_player(player, i):
    if player in playertypes:
        return playertypes[player](names[i], i)
    elif player.startswith("self("):
        other = player[5:-1]
        return SelfRecognitionPlayer(names[i], i, playertypes[other])
    elif player.startswith("sample("):
        other = player[7:-1]
        if "," in other:
            othername, maxtime = other.split(",")
            othername = othername.strip()
            maxtime = int(maxtime.strip())
            return SamplingRecognitionPlayer(names[i], i, playertypes[othername], maxtime=maxtime)
        return SamplingRecognitionPlayer(names[i], i, playertypes[other])
    return None 
    
def main(args, n=10000):
    if not args:
        args = ["random"]*3
    if args[0] == "trial":
        treatments = [["intentional", "intentional"], ["intentional", "outer"], ["outer", "outer"]]
        #[["sample(intentional, 50)", "sample(intentional, 50)"], ["sample(intentional, 100)", "sample(intentional, 100)"]] #, ["self(intentional)", "self(intentional)"], ["self", "self"]]
        results = []
        print treatments
        for i in xrange(int(args[1])):
            result = []
            times = []
            avgtimes = []
            print "trial", i+1
            for t in treatments:
                random.seed(i)
                players = []
                for i,player in enumerate(t):
                    players.append(make_player(player,i))
                g = Game(players, NullStream())
                t0 = time.time()
                result.append(g.run())
                times.append(time.time() - t0)
                avgtimes.append(times[-1]*1.0/g.turn)
                print ".",
            print
            print "scores:",result
            print "times:", times
            print "avg times:", avgtimes
        
        return
        
        
    players = []
    
    for i,a in enumerate(args):
        players.append(make_player(a, i))
        
    out = NullStream()
    if n < 3:
        out = sys.stdout
    pts = []
    for i in xrange(n):
        if (i+1)%100 == 0:
            print "Starting game", i+1
        random.seed(i+1)
        g = Game(players, out)
        try:
            pts.append(g.run())
            if (i+1)%100 == 0:
                print "score", pts[-1]
        except Exception:
            import traceback
            traceback.print_exc()
    if n < 10:
        print pts
    import numpy
    print "average:", numpy.mean(pts)
    print "stddev:", numpy.std(pts, ddof=1)
    print "range", min(pts), max(pts)
    
    
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='An implementation of Hanabi.')
    parser.add_argument('players', metavar='P', type=str, nargs='*',
                        help='')
    parser.add_argument('--count', "-n", dest='n', action='store',
                        default=10000, type=int,
                        help='How many games to play (default: 10000)')

    args = parser.parse_args()
    main(args.players, args.n)