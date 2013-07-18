from flask import flash

import sys
sys.path.append('..')
sys.path.append('/usr/lib/graphviz/python/')
sys.path.append('/usr/lib64/graphviz/python/')


# Import pygraph
from pygraph.classes.graph import graph
from pygraph.classes.digraph import digraph
from pygraph.algorithms.searching import breadth_first_search
from pygraph.algorithms.cycles import find_cycle



class UpdateRequest(object):
	def __init__(self):
		self.group = digraph()

	def all_edges(self):
		edges = self.group.edges()
		results = []
		for e in edges:
			results.append((e[0], e[1], self.group.edge_weight(e)))
		return results

	def form_graph(self, nodes, edges, weights):
		if len(nodes) == 0:
			return "empty graph"
		elif len(edges) != len(weights):
			return "please check the list"
		else:
			self.group.add_nodes(nodes)
			for i in range(0, len(weights)):
				self.group.add_edge(edges[i], wt=weights[i])
		

	def update_group(self):

		weights = []

		#delete 0 edges

		all_edges = self.group.edges()
		for e in all_edges:
			if self.group.edge_weight(e) == 0:
				self.group.del_edge(e)

		#find cyclesprint track
		cycle = find_cycle(self.group)

		if len(cycle) == 0:
			# check for chains

			all_nodes = self.group.nodes()

			t = []
			w = 0

			def helper(node, weight):
				neighbors = self.group.neighbors(node)
				if len(neighbors) == 0:
					return track
				else:
					for i in neighbors:
						if weight == self.group.edge_weight((node, i)):
							track.append((node, i))
							return helper(i, weight)
					return track

			for n in all_nodes:	
				neighbors = self.group.neighbors(n)
				for i in neighbors:
					track = [(n, i)]
					temp = self.group.edge_weight((n, i))
					track = helper(i, temp)
					if len(track) > 1:
						t = track
						w = temp
						break

			print "y", t

			if len(t) <= 1:
				return False
			
			for e in t:
				self.group.del_edge(e)

			self.add_record(str(t[0][0]), str(t[-1][1]), w)

		else:
			#find min weight
			for i in range(0, len(cycle)):

				if i == len(cycle) - 1:
					w = self.group.edge_weight((cycle[i], cycle[0]))
					weights.append(w)
				else:
					w = self.group.edge_weight((cycle[i], cycle[i+1]))
					weights.append(w)

			min_weights = min(weights)

			#update edge

			for i in range(0, len(cycle)):

				if i == len(cycle) - 1:
					edge = (cycle[i], cycle[0])
				else:
					edge = (cycle[i], cycle[i+1])

				w = self.group.edge_weight(edge)
				self.group.set_edge_weight(edge, w - min_weights)

			return True


		dot = write(self.group)
		gvv = gv.readstring(dot)
		gv.layout(gvv,'dot')
		gv.render(gvv,'png','1-after.png')

	def add_record(self, borrower, lender, amount):
		if amount == 0:
			flash("please enter correct number")
			return False
		edge = (borrower, lender)
		#edge already exists
		print "all edges:" , self.all_edges()
		print "add:", (borrower, lender)
		print amount
		print self.group.has_edge((borrower, lender))

		if self.group.has_edge((borrower, lender)):
			edge_weight = self.group.edge_weight(edge)
			self.group.set_edge_weight(edge, edge_weight + amount)
			print "yes"
		#negative edge direction exists
		elif self.group.has_edge((lender, borrower)):
			edge_weight = amount
			existing_weight = self.group.edge_weight((lender, borrower))
			if edge_weight > existing_weight:
				self.group.add_edge((borrower, lender), wt=amount - existing_weight)
				self.group.del_edge((lender, borrower))
				print ">"
			else:
				self.group.set_edge_weight((lender, borrower), existing_weight - amount)
				print "<", edge_weight - amount

		else:
		#edge does not exist
			self.group.add_edge((borrower, lender), wt=amount)

		while self.update_group() != False:
			print "y"





