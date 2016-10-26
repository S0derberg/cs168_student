"""Your awesome Distance Vector router for CS 168."""

import sim.api as api
import sim.basics as basics

# We define infinity as a distance of 16.
INFINITY = 16


class DVRouter(basics.DVRouterBase):
    # NO_LOG = True # Set to True on an instance to disable its logging
    # POISON_MODE = False # Can override POISON_MODE here
    # DEFAULT_TIMER_INTERVAL = 5 # Can override this yourself for testing

    def __init__(self):
        """
        Called when the instance is initialized.

        You probably want to do some additional initialization here.

        """
        self.start_timer()  # Starts calling handle_timer() at correct rate
        Hosts = []
        #{Port: Neigbor}
        self.Neighbors = {}
        self.Timers = {}
        #Example DV {A: (3, C), B: (9, A), C: (2, D), D: (0, D), E: (3, D)} 
        self.DV = {}
        self.PtoL = {}



    def handle_link_up(self, port, latency):
        """
        Called by the framework when a link attached to this Entity goes up.

        The port attached to the link and the link latency are passed
        in.

        """
        self.PtoL[port] = latency

        for place in self.DV.keys(): #{Host: (1, 0), otherHost: (4, 1)}
            best_cost, next_hop = self.DV[place] #cant poison anything or stuff here because no way should any routes use this link yet.
            newRoute = basics.RoutePacket(place, best_cost)
            # Send the update packet from self

            self.send(newRoute, port)

        # Let the router on the other side know who I am, so they can add me to their neighbors
        newNeighbor = basics.RoutePacket(self, 0)
        self.send(newNeighbor, port)


    def handle_link_down(self, port):
        """
        Called by the framework when a link attached to this Entity does down.

        The port number used by the link is passed in.

        """
        del self.PtoL[port]
        if port in self.Neighbors.keys():
            if self.POISON_MODE: #Poisoning Route
                for live_port in self.PtoL.keys():
                    for place in self.DV.keys():
                        best_cost, next_hop = self.DV[place]
                        if next_hop == port:
                            newRoute = basics.RoutePacket(place, INFINITY)
                            self.send(newRoute, live_port)

            del self.Neighbors[port]

    def handle_rx(self, packet, port):
        """
        Called by the framework when this Entity receives a packet.

        packet is a Packet (or subclass).
        port is the port number it arrived on.

        You definitely want to fill this in.

        """
        #self.log("RX %s on %s (%s)", packet, port, api.current_time())
        if isinstance(packet, basics.RoutePacket): #remember to log info for 15 seconds. 
            # update_source is the router from which the routing update came from
            # Get a list of all destinations with paths announced in this message.
 
            dst = packet.destination     

            # Handle a packet that is just telling me about a new neighbor router
            if (isinstance(dst, DVRouter)):
                self.Neighbors[port] = packet.src
                return

            # Handle poison
            if self.POISON_MODE and packet.latency == INFINITY:
                best_cost, next_hop = self.DV[dst]
                if next_hop == port:
                    self.DV[dst] = (INFINITY, next_hop)
                    #self.handle_timer()
                    for port in self.PtoL.keys():
                        best_cost, next_hop = self.DV[dst]

                        # Split Horizon Simple
                        if not self.POISON_MODE and next_hop == port:
                            continue

                        if self.POISON_MODE: 
                            if next_hop == port: #poisoned Reverse split horizon
                                newRoute = basics.RoutePacket(dst, INFINITY)
                            else:
                                newRoute = basics.RoutePacket(dst, best_cost)
                        else:
                            newRoute = basics.RoutePacket(dst, best_cost)

                        # Send the update packet from self
                        self.send(newRoute, port)
                    del self.DV[dst]

            #check if this has been reached. Then replacement procedure
            if dst not in self.DV.keys():
                self.DV[dst] = (INFINITY, None)
            cost_s_ups = self.PtoL[port]
            cost_ups_d = packet.latency
            if cost_ups_d + cost_s_ups < INFINITY and self.DV[dst][0] > cost_s_ups + cost_ups_d:
                self.DV[dst] = (cost_ups_d + cost_s_ups, port)
                self.Timers[(port, packet.destination)] = api.current_time()
                #self.handle_timer()
                for port in self.PtoL.keys():
                    best_cost, next_hop = self.DV[dst]

                    # Split Horizon Simple
                    if not self.POISON_MODE and next_hop == port:
                        continue

                    if self.POISON_MODE: 
                        if next_hop == port: #poisoned Reverse split horizon
                            newRoute = basics.RoutePacket(dst, INFINITY)
                        else:
                            newRoute = basics.RoutePacket(dst, best_cost)
                    else:
                        newRoute = basics.RoutePacket(dst, best_cost)

                    # Send the update packet from self
                    self.send(newRoute, port)



            # ALGORITHM:
            # First we find grab packets destination and latency. 
            #Then we look to see if destination has already been logged in DV
            #if Not instantiate it.
            #then check to ensure source in DV
            #grab distance from source to me
            #grab distance from me to destination
            #if DV currently is larger but less than INF, replace it

            # If cost_from_source_to_update_source + (cost_from_update_source_to_destination) < cost_from_self_to_destination
            #       (from dictionary)                     (from call to get_distance)                 (from iteration)

            # If the above equality is true, we update our routing table and set nextHop to update_source

            # Returns destinations from current router, along with the cost/next hop to these destinations
            # extracted part is {A: (3, C), B: (9, A), C: (2, D), D: (0, D), E: (3, D)}
  

        elif isinstance(packet, basics.HostDiscoveryPacket):
                # (1) add this newly discovered neighbor to the list of neighbors for 'this' DVRouter
                self.Neighbors[port] = packet.src

                # (2) update the cost from 'this' DVRouter to this newly discovered neighbor in our routing table
                self.DV[packet.src] = (self.PtoL[port], port) # Could set it to 0 or 1?
        else:
            if (packet.dst) not in self.DV.keys(): #cant get there
                return
            elif self.DV[packet.dst][0] < INFINITY:
                if self.DV[packet.dst][1] == port:
                    return
                self.send(packet, self.DV[packet.dst][1]) #send on its way
            else:
                return #got inifinty problem 

    def handle_timer(self):
        """
        Called periodically.

        When called, your router should send tables to neighbors.  It
        also might not be a bad place to check for whether any entries
        have expired.

        """
        #Checking Timers. This is what we had earlier. 
        copy = self.Timers.copy()
        for i in self.Timers.keys():
            if api.current_time() >= self.Timers[i] + self.ROUTE_TIMEOUT:
                old_port = self.DV[i[1]][1]
                self.DV[i[1]] = (INFINITY, old_port)
                del copy[i]

        self.Timers = copy.copy()

        #Send tables to neighbors
        # These are the neighbors that we will be sending updates to   {Host: 0, 1: 1, 2: 2}

        for port in self.PtoL.keys():
            if port in self.Neighbors.keys():
                if isinstance(self.Neighbors[port], basics.BasicHost):
                # Do not send any updates to BasicHost
                    if self.DV[self.Neighbors[port]][0] == INFINITY and self.PtoL[port] < INFINITY:
                        self.DV[self.Neighbors[port]] = (self.PtoL[port], port)
                    continue
            for place in self.DV.keys():
                best_cost, next_hop = self.DV[place]

                if best_cost == INFINITY:
                    continue

                # Split Horizon Simple
                if not self.POISON_MODE and next_hop == port:
                    continue

                if self.POISON_MODE: 
                    if next_hop == port: #poisoned Reverse split horizon
                        newRoute = basics.RoutePacket(place, INFINITY)
                    else:
                        newRoute = basics.RoutePacket(place, best_cost)
                else:
                    newRoute = basics.RoutePacket(place, best_cost)

                # Send the update packet from self
                self.send(newRoute, port)



 
