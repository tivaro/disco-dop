from nltk import Tree, ImmutableTree
from collections import defaultdict
import codecs
def label(tree, sent):
	if isinstance(tree, Tree):
		return tree.node.replace("$", r"\$").replace("[", "(").replace("<","{").replace(">","}").replace("-",",").replace("|","_")
	else: return "%s" % sent[int(tree)]
	#"\\fontsize{4}{5}\\selectfont"

def tikzdtree(tree, sent):
	#assert len(tree.leaves()) == len(sent)
	#assert sorted(tree.leaves()) == range(len(sent))
	for a in list(tree.subtrees(lambda n: isinstance(n[0], Tree)))[::-1]:
		a.sort(key=lambda n: n.leaves())
	result = [r"\begin{tikzpicture}[scale=0.5,"
	r"	cross line/.style={preaction={draw=white, -, line width=6pt}}]",
	r"\tiny\sffamily", r"\path"]
	scale = 2
	count = 0
	ids = {}
	crossed = set()
	zeroindex = 0 if 0 in tree.leaves() else 1
	positions = tree.treepositions()
	depth = max(map(len, positions)) + 1
	matrix = [[None for _ in scale*sent] for _ in range(scale*depth)]
	children = defaultdict(list)

	# add each unary above its child
	for n in range(depth):
		nodes = sorted(a for a in positions if len(a) == n)
		for m in nodes:
			if isinstance(tree[m], Tree) and len(tree[m]) == 1:
				#i = tree[m].leaves()[0] - zeroindex
				l = [a*scale for a in tree[m].leaves()]
				i = min(l) + (max(l) - min(l)) / 2
				if not isinstance(tree[m][0], Tree):
					matrix[(depth - 2) * scale][i] = m
				else:
					matrix[n * scale][i] = m
				children[m[:-1]].append(i)

	# add other nodes centered on their children, 
	# if the center is already taken, back off
	# to the left and right alternately, until an empty cell is found.
	for n in range(depth - 1, -1, -1):
		nodes = sorted(a for a in positions if len(a) == n)
		for m in nodes[::-1]:
			if isinstance(tree[m], Tree):
				if len(tree[m]) == 1: continue
				l = [a*scale for a in tree[m].leaves()]
				#l = [a for a in children[m]]
				center = min(l) + (max(l) - min(l)) / 2
				i = j = center
			else:
				i = j = (int(tree[m]) - zeroindex) * scale
				matrix[(depth - 1) * scale][i] = m
				children[m[:-1]].append(i)
				continue
			while i < scale * len(sent) or j > zeroindex:
				if (i < scale * len(sent) and not matrix[n*scale][i]
					and (not matrix[-scale][i]
					or matrix[-scale][i][:len(m)] == m)):
					break
				if (j > zeroindex and not matrix[n*scale][j]
					and (not matrix[-scale][i]
					or matrix[-scale][i][:len(m)] == m)):
					i = j
					break
				i += 1
				j -= 1
			if not zeroindex <= i < scale * len(sent):
				raise ValueError("couldn't find location for node")
			shift = 0
			if n+1 < len(matrix) and children[m]:
				pivot = min(children[m])
				if (set(a[:-1] for a in matrix[(n+1)*scale][:pivot] if a and a[:-1] != i) &
				(set(a[:-1] for a in matrix[(n+1)*scale][pivot:] if a and a[:-1] != i))):
					shift = 1
					crossed.add(m)
			matrix[n * scale + shift][i] = m
			children[m[:-1]].append(i)

	# remove unused columns
	for m in range(scale * len(sent) - 1, -1, -1):
		if not any(isinstance(matrix[n][m], tuple) for n in range(depth)):
			#for n in range(depth): del matrix[n][m]
			pass

	# remove unused rows
	deleted = 0
	for n in range(scale * depth - 1, 0, -1):
		if not any(matrix[n]):
			del matrix[n]
			deleted += 1

	# write nodes with coordinates
	for n, _ in enumerate(matrix):
		for m, i in enumerate(matrix[n]):
			if isinstance(i, tuple):
				d = scale * depth - n - deleted - 1
				if d == 1: d = 0.75
				result.append("\t(%d, %g) node (n%d) {%s}"
					% (m, d, count, label(tree[i], sent)))
				ids[i] = "n%d" % count
				count += 1
	result += [";"]

	# write branches from node to node
	for i in reversed(positions):
		if not isinstance(tree[i], Tree): continue
		iscrossed = any(a[:-1] == i for a in crossed)
		shift = -0.5
		for j, child in enumerate(tree[i] if iscrossed else ()):
			result.append(
				"\draw [white, -, line width=6pt] (%s) -- +(0, %g) -| (%s);"
				% (ids[i], shift, ids[i + (j,)]))
		for j, child in enumerate(tree[i]):
			result.append("\draw (%s) -- +(0, %g) -| (%s);"
				% (ids[i], shift, ids[i + (j,)]))
	result += [r"\end{tikzpicture}"]
	return "\n".join(result)

def main():
	from itertools import count
	trees = """(S (NP (NN 1) (EX 3)) (VP (VB 0) (JJ 2)))
	(ROOT (S (ADV 0) (VVFIN 1) (VP (PP (APPR 2) (PIAT 3) (NN 4)) (NP (ART 8) (NN 9)) (VZ (PTKZU 10) (VVINF 11))) (NP (AP (PTKNEG 5) (ADJA 6)) (NN 7))) ($. 12))
	(ROOT (S (S|<NP> (NP (AP (PTKNEG 5) (ADJA 6)) (NN 7)) (S|<VP> (VP (VP|<PP> (PP (PP|<NN> (NN 4) (PP|<PIAT> (PIAT 3) (PP|<APPR> (APPR 2))))) (VP|<NP> (NP (ART 8) (NN 9)) (VP|<VZ> (VZ (PTKZU 10) (VVINF 11)))))) (S|<ADV> (ADV 0) (S|<VVFIN> (VVFIN 1)))))) ($. 12))
	(ROOT (S (ADV 0) (VVFIN 1) (NP (PDAT 2) (NN 3)) (PTKNEG 4) (PP (APPRART 5) (NN 6) (NP (ART 7) (ADJA 8) (NN 9)))) ($. 10))"""
	sents = """is/VB Mary/PN happy/JJ there/EX
	Vielmehr/ADV scheinen/VVFIN auf/APPR allen/PIAT Seiten/NN nicht/PTKNEG unerhebliche/ADJA Eigeninteressen/NN das/ART Handeln/NN zu/PTKZU bestimmen/VVINF ./$.
	Vielmehr/ADV scheinen/VVFIN auf/APPR allen/PIAT Seiten/NN nicht/PTKNEG unerhebliche/ADJA Eigeninteressen/NN das/ART Handeln/NN zu/PTKZU bestimmen/VVINF ./$.
	Leider/ADV stehen/VVFIN diese/PDAT Fragen/NN nicht/PTKNEG im/APPRART Vordergrund/NN der/ART augenblicklichen/ADJA Diskussion/NN ./$."""
	trees = [Tree.parse(a, parse_leaf=int) for a in trees.splitlines()]
	sents = [[w.split("/")[0] for w in a.split()] for a in sents.splitlines()]
	for n, tree, sent in zip(count(1), trees, sents):
		print "tree", tree
		print "sent", sent, "\n"
		codecs.open("/tmp/tree%d.tex" % n, "w", encoding='utf-8').write(tikzdtree(tree, sent))

if __name__ == '__main__': main()