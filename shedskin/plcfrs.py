# probabilistic CKY parser for Simple Range Concatenation Grammars
# (equivalent to Linear Context-Free Rewriting Systems)
# shedskin version^Wattempt
from math import exp, log
from collections import defaultdict
from pq import heapdict
from items import ChartItem, Edge, Terminal, Rule #NoChartItem
from bit import *
print "plcfrs in shedskin mode" #how to detect whether we're running compiled?
NONE = ChartItem(0, 0) #NoChartItem()

def parse(sent, grammar, tags, root, viterbi, n, estimate):
	""" parse sentence, a list of tokens, optionally with gold tags, and
	produce a chart, either exhaustive (n=0) or up until the viterbi parse
	NB: viterbi & estimate parameters are ignored in this version
	"""
	unary = grammar.unary
	lbinary = grammar.lbinary
	rbinary = grammar.rbinary
	lexical = dict(grammar.lexical)
	toid = dict(grammar.toid)
	tolabel = dict(grammar.tolabel)
	goal = ChartItem(root, (1 << len(sent)) - 1)
	m = maxA = 0
	C, Cx = {}, {}
	A = heapdict()

	# type inference hints:
	A[ChartItem(0, 0)] = Edge(0.0, 0.0, ChartItem(0, 0), ChartItem(0, 0))
	A[ChartItem(0, 0)] = Edge(0.0, 0.0, ChartItem(0, 0), NONE)
	C[ChartItem(0, 0)] = [Edge(0.0, 0.0, ChartItem(0, 0), ChartItem(0, 0))]
	C[ChartItem(0, 0)] = [Edge(0.0, 0.0, ChartItem(0, 0), NONE)]
	Cx[0] = { ChartItem(0, 0) : 0.0 }
	Cx.popitem(); C.popitem(); A.popitem()

	# scan
	Epsilon = toid["Epsilon"]
	for i, w in enumerate(sent):
		recognized = False
		for rule in lexical.get(w, []):
			if not tags or tags[i] == tolabel[rule.lhs].split("@")[0]:
				Ih = ChartItem(rule.lhs, 1 << i)		# tag & bitvector
				I = ChartItem(Epsilon, i)			# word index
				# if gold tags were provided, give them probability of 1
				A[Ih] = Edge(0.0 if tags else rule.prob,
							0.0 if tags else rule.prob, I, NONE)
				recognized = True
		if not recognized and tags and tags[i] in toid:
			Ih = ChartItem(toid[tags[i]], 1 << i)
			I = ChartItem(Epsilon, i)
			A[Ih] = Edge(0.0, 0.0, I, NONE)
			recognized = True
			continue
		elif not recognized:
			print "not covered:", tags[i] if tags else w
	# parsing
	while A:
		Ih, edge = A.popitem()
		C.setdefault(Ih, []).append(edge)
		Cx.setdefault(Ih.label, {})[Ih] = edge.inside

		if Ih == goal:
			m += 1
			if viterbi and n == m: break
		else:
			for I1h, edge in deduced_from(Ih, edge.inside, Cx,
											unary, lbinary, rbinary):
				# I1h = new ChartItem that has been derived.
				# scores: oscore, iscore, p, rhs
				# 	oscore = estimate of total score; NB not present here
				#			(outside estimate + inside score up till now)
				# 	iscore = inside score,
				# 	p = rule probability,
				# 	rhs = backpointers to 1 or 2 ChartItems that led here (I1h)
				# explicit get to avoid inserting spurious keys
				if I1h not in Cx.get(I1h.label, {}) and I1h not in A:
					# haven't seen this item before, add to agenda
					A[I1h] = edge
				elif I1h in A:
					# either item has lower score, update agenda,
					# or extend chart
					if edge.inside < A[I1h].inside:
						C.setdefault(I1h, []).append(A[I1h])
						A[I1h] = edge
					else:
						C.setdefault(I1h, []).append(edge)
				else:
					C[I1h].append(edge)
		maxA = max(maxA, len(A))
	print "max agenda size", maxA, "/ chart keys", len(C),
	print "/ values", sum(map(len, C.values()))
	return (C, goal) if goal in C else ({}, NONE)

def deduced_from(Ih, x, Cx, unary, lbinary, rbinary):
	I = Ih.label; Ir = Ih.vec
	result = []
	for rule in unary[I]:
		result.append((ChartItem(rule.lhs, Ir),
					Edge(x + rule.prob, rule.prob, Ih, NONE)))
	for rule in lbinary[I]:
		for I1h, y in Cx.get(rule.rhs2, {}).items():
			if concat(rule.yf, Ir, I1h.vec):
				result.append((ChartItem(rule.lhs, Ir ^ I1h.vec),
					Edge(x + y + rule.prob, rule.prob, Ih, I1h)))
	for rule in rbinary[I]:
		for I1h, y in Cx.get(rule.rhs1, {}).items():
			if concat(rule.yf, I1h.vec, Ir):
				result.append((ChartItem(rule.lhs, I1h.vec ^ Ir),
					Edge(x + y + rule.prob, rule.prob, I1h, Ih)))
	return result

def concat(yieldfunction, lvec, rvec):
	if lvec & rvec: return False
	lpos = nextset(lvec, 0)
	rpos = nextset(rvec, 0)
	# if there are no gaps in lvec and rvec, and the yieldfunction is the
	# concatenation of two elements, then this should be quicker
	if (lvec >> nextunset(lvec, lpos) == 0
		and rvec >> nextunset(rvec, rpos) == 0):
		if yieldfunction == ((0, 1),):
			return bitminmax(lvec, rvec)
		elif yieldfunction == ((1, 0),):
			return bitminmax(rvec, lvec)
	#this algorithm taken from rparse FastYFComposer.
	for arg in yieldfunction:
		m = len(arg) - 1
		for n, b in enumerate(arg):
			if b == 0:
				# check if there are any bits left, and
				# if any bits on the right should have gone before
				# ones on this side
				if lpos == -1 or (rpos != -1 and rpos <= lpos):
					return False
				# jump to next gap
				lpos = nextunset(lvec, lpos)
				# there should be a gap if and only if
				# this is the last element of this argument
				if rpos != -1 and rpos < lpos: return False
				if n == m:
					if testbit(rvec, lpos): return False
				elif not testbit(rvec, lpos): return False
				#jump to next argument
				lpos = nextset(lvec, lpos)
			elif b == 1:
				# vice versa to the above
				if rpos == -1 or (lpos != -1 and lpos <= rpos):
					return False
				rpos = nextunset(rvec, rpos)
				if lpos != -1 and lpos < rpos: return False
				if n == m:
					if testbit(lvec, rpos): return False
				elif not testbit(lvec, rpos): return False
				rpos = nextset(rvec, rpos)
			else: raise ValueError("non-binary element in yieldfunction")
	if lpos != -1 or rpos != -1:
		return False
	# everything looks all right
	return True

def mostprobablederivation(chart, start, tolabel):
	""" produce a string representation of the viterbi parse in bracket
	notation"""
	if start not in chart: return 0.0, str(start.vec) if start else ''	
	return chart[start][0].inside, '(%s %s)' % (tolabel[start.label],
		" ".join([mostprobablederivation(chart, child, tolabel)[1]
			for child in (chart[start][0].left, chart[start][0].right)
			if not child is NONE]))

def pprint_chart(chart, sent, tolabel):
	print "chart:"
	for a in sorted(chart, key=lambda x: bitcount(x.vec)):
		print "%s[%s] =>" % (tolabel[a.label],
					("0" * len(sent) + bin(a.vec)[2:])[::-1][:len(sent)])
		for edge in chart[a]:
			for c in (edge.left, edge.right):
				if c is NONE: continue
				if tolabel[c.label] == "Epsilon":
					print "\t", repr(sent[edge.left.vec]),
				else:
					print "\t%s[%s]" % (tolabel[c.label],
						("0" * len(sent) + bin(c.vec)[2:])[::-1][:len(sent)]),
			print "\t",exp(-edge.inside)
		print

def do(sent, grammar):
	print "sentence", sent
	root = grammar.toid['S']
	chart, start = parse(sent.split(), grammar, None, root, True, 1, None)
	pprint_chart(chart, sent.split(), grammar.tolabel)
	if chart:
		#for a, p in mostprobableparse(chart, start, grammar.tolabel,
		#													n=1000).items():
		#	print p, a
		p, a = mostprobablederivation(chart, start, grammar.tolabel)
		print exp(-p), a, '\n'
		return True
	else:
		print "no parse\n"
		return False

class Grammar(object):
	__slots__ = ('unary', 'lbinary', 'rbinary', 'lexical',
					'bylhs', 'toid', 'tolabel')
	def __init__(self, unary, lbinary, rbinary, lexical, bylhs, toid, tolabel):
		self.unary = unary
		self.lbinary = lbinary
		self.rbinary = rbinary
		self.lexical = lexical
		self.bylhs = bylhs
		self.toid = toid
		self.tolabel = tolabel

def main():
	'''
	grammar = splitgrammar(
		[((('S','VP2','VMFIN'),    ((0,1,0),)),  0.0),
		((('VP2','VP2','VAINF'),  ((0,),(0,1))), log(0.5)),
		((('VP2','PROAV','VVPP'), ((0,),(1,))), log(0.5)),
		((('PROAV', 'Epsilon'), ('Daruber', ())), 0.0),
		((('VAINF', 'Epsilon'), ('werden', ())), 0.0),
		((('VMFIN', 'Epsilon'), ('muss', ())), 0.0),
		((('VVPP', 'Epsilon'), ('nachgedacht', ())), 0.0)])
	'''
	# output of splitgrammar:
	unary = [[], [], [], [], [], [], [], []]
	lbinary = [[], [],
		[Rule(6, 2, 7, [[0], [1]], 0.69314718055994529)],
		[], [], [],
		[Rule(3, 6, 5, [[0, 1, 0]], 0.0),
		Rule(6, 6, 4, [[0], [0, 1]], 0.69314718055994529)], []]
	rbinary = [[], [], [], [],
		[Rule(6, 6, 4, [[0], [0, 1]], 0.69314718055994529)],
		[Rule(3, 6, 5, [[0, 1, 0]], 0.0)], [],
		[Rule(6, 2, 7, [[0], [1]], 0.69314718055994529)]]
	#bylhs = [[], [], [(((2, 0), ('Daruber', ())), 0.0)], [(((3, 6, 5), ((0, 1, 0),)), 0.0)], [(((4, 0), ('werden', ())), 0.0)], [(((5, 0), ('muss', ())), 0.0)], [(((6, 6, 4), ((0,), (0, 1))), 0.69314718055994529), (((6, 2, 7), ((0,), (1,))), 0.69314718055994529)], [(((7, 0), ('nachgedacht', ())), 0.0)]]
	bylhs = [] #not needed here
	lexical = { 'muss': [Terminal(5, 0, ['muss', []], 0.0)],
				'werden': [Terminal(4, 0, ['werden', []], 0.0)],
				'Daruber': [Terminal(2, 0, ['Daruber', []], 0.0)],
				'nachgedacht': [Terminal(7, 0, ['nachgedacht', []], 0.0)] }
	toid = {'VP2': 6, 'Epsilon': 0, 'VVPP': 7, 'S': 3, 'VMFIN': 5, 'VAINF': 4,
		'ROOT': 1, 'PROAV': 2 }
	tolabel = {0: 'Epsilon', 1: 'ROOT', 2: 'PROAV', 3: 'S', 4: 'VAINF', 5:
		'VMFIN', 6: 'VP2', 7: 'VVPP'}
	grammar = Grammar(unary, lbinary, rbinary, lexical, bylhs, toid, tolabel)

	daruber = ChartItem(toid['PROAV'], 0b0001)
	nachgedacht = ChartItem(toid['VVPP'], 0b0100)
	vp = ChartItem(toid['VP2'], 0b0101)
	vp2 = ChartItem(toid['VP2'], 0b0101)
	assert vp == vp2
	w1 = Edge(0.0, 0.0, ChartItem(0, 0), NONE)
	w3 = Edge(0.0, 0.0, ChartItem(0, 2), NONE)
	edge = Edge(-log(0.5), -log(0.5), daruber, nachgedacht)
	C = { vp2 : [edge], daruber : [w1], nachgedacht : [w3] }
	Cx = {}; Cx[toid['PROAV']] = { daruber : 0.0 }
	pprint_chart(C, "Daruber muss nachgedacht werden".split(), tolabel)
	assert deduced_from(nachgedacht, 0.0, Cx, unary,lbinary,rbinary) == [(vp2, edge)]
	lvec = 0b0011; rvec = 0b1000; yieldfunction = [[0], [1]]
	assert concat([[0], [1]], lvec, rvec)
	assert not concat([[0, 1]], lvec, rvec)
	assert not concat([[1], [0]], lvec, rvec)
	assert (mostprobablederivation(C, vp2, tolabel)
				== (-log(0.5), '(VP2 (PROAV 0) (VVPP 2))'))
	chart, start = parse("Daruber muss nachgedacht werden".split(), grammar,
					"PROAV VMFIN VVPP VAINF".split(), toid['S'], True, 1, None)
	assert (mostprobablederivation(chart, start, tolabel) ==
		(-log(0.25), '(S (VP2 (VP2 (PROAV 0) (VVPP 2)) (VAINF 3)) (VMFIN 1))'))

	assert do("Daruber muss nachgedacht werden", grammar)
	assert do("Daruber muss nachgedacht werden werden", grammar)
	assert do("Daruber muss nachgedacht werden werden werden", grammar)
	#should print 'no parse':
	assert not do("muss Daruber nachgedacht werden", grammar)
	print 'it worked'
if __name__ == '__main__': main()
