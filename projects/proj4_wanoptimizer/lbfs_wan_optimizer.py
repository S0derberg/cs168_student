import wan_optimizer
import utils
import tcp_packet

class WanOptimizer(wan_optimizer.BaseWanOptimizer):
    """ WAN Optimizer that divides data into variable-sized
    blocks based on the contents of the file.

    This WAN optimizer should implement part 2 of project 4.
    """

    # The string of bits to compare the lower order 13 bits of hash to
    GLOBAL_MATCH_BITSTRING = '0111011001010'

    def __init__(self):
        wan_optimizer.BaseWanOptimizer.__init__(self)
        # Add any code that you like here (but do not add any constructor arguments).
        self.buffers = {}
        self.data = {}
        return

    # Break a packet with too big of a payload into conforming size packets.
    def send_large(self, packet, port):
        content = packet.payload
        while (len(content) > utils.MAX_PACKET_SIZE):
            pack = tcp_packet.Packet(packet.src, packet.dest, True, False, content[:utils.MAX_PACKET_SIZE])
            content = content[utils.MAX_PACKET_SIZE:]
            self.send(pack, port)

        if len(content) >= 0:
            if packet.is_fin:
                pack = tcp_packet.Packet(packet.src, packet.dest, True, True, content)
            else:
                pack = tcp_packet.Packet(packet.src, packet.dest, True, False, content)
            self.send(pack, port)


    # Handle a packet with the fin flag set
    def handle_fin(self, packet, flow, port):
        block_size = self.find_delimiter(self.buffers[flow], True)

        overflow = block_size < len(self.buffers[flow])
        if overflow:
            key = utils.get_hash(self.buffers[flow][:block_size])
        else:
            key = utils.get_hash(self.buffers[flow])

        if key in self.data.keys():
            packet.payload = key
            packet.is_raw_data = False
            if overflow:
                self.buffers[flow] = self.buffers[flow][block_size:]
                packet.is_fin = False
                self.send(packet, port)
                next_packet = tcp_packet.Packet(packet.src, packet.dest, True, True, self.buffers[flow])
                self.handle_fin(next_packet, flow, port)
            else:
                self.buffers[flow] = ""
                self.send(packet, port)
        else:
            if overflow:
                self.data[key] = self.buffers[flow][:block_size]
                self.buffers[flow] = self.buffers[flow][block_size:]
                packet.payload = self.data[key]
                packet.is_fin = False
                self.send_large(packet, port)
                next_packet = tcp_packet.Packet(packet.src, packet.dest, True, True, self.buffers[flow])
                self.handle_fin(next_packet, flow, port)
            else:
                self.data[key] = self.buffers[flow]
                self.buffers[flow] = ""
                packet.payload = self.data[key]
                self.send_large(packet, port)

    # Find a delimiter in a block and return how many bytes are up to and including the
    # delimiter.  Return 0 if no delimiter found
    def find_delimiter(self, data, fin=False):
        if len(data) < 48:
            if fin:
                return len(data)
            else:
                return 0

        start = 0
        end = 48
        window = data[start:end]
        while (utils.get_last_n_bits(utils.get_hash(window), 13) != WanOptimizer.GLOBAL_MATCH_BITSTRING):
            if len(data) == end:
                if fin:
                    return len(data)
                else:
                    return 0
            else:
                start += 1
                end += 1
                window = data[start:end]

        return end

    def receive(self, packet):
        """ Handles receiving a packet.

        Right now, this function simply forwards packets to clients (if a packet
        is destined to one of the directly connected clients), or otherwise sends
        packets across the WAN. You should change this function to implement the
        functionality described in part 2.  You are welcome to implement private
        helper functions that you call here. You should *not* be calling any functions
        or directly accessing any variables in the other middlebox on the other side of 
        the WAN; this WAN optimizer should operate based only on its own local state
        and packets that have been received.
        """

        flow = (packet.src, packet.dest)

        if packet.dest in self.address_to_port:
            # The packet is destined to one of the clients connected to this middlebox;
            # send the packet there.

            if not packet.is_raw_data:
                packet.payload = self.data[packet.payload]
                self.send_large(packet, self.address_to_port[packet.dest])
            else:
                if flow not in self.buffers.keys():
                    self.buffers[flow] = packet.payload
                else:
                    self.buffers[flow] = self.buffers[flow] + packet.payload

                block_size = self.find_delimiter(self.buffers[flow])
                if (not block_size and not packet.is_fin):
                    return
                elif packet.is_fin:
                    self.handle_fin(packet, flow, self.address_to_port[packet.dest])
                else:
                    key = utils.get_hash(self.buffers[flow][:block_size])
                    self.data[key] = self.buffers[flow][:block_size]
                    self.buffers[flow] = self.buffers[flow][block_size:]
                    packet.payload = self.data[key]
                    self.send_large(packet, self.address_to_port[packet.dest])

        else:
            # The packet must be destined to a host connected to the other middlebox
            # so send it across the WAN.
            if flow not in self.buffers.keys():
                self.buffers[flow] = packet.payload
            else:
                self.buffers[flow] = self.buffers[flow] + packet.payload

            block_size = self.find_delimiter(self.buffers[flow])
            if (not block_size and not packet.is_fin):
                return
            elif packet.is_fin:
                self.handle_fin(packet, flow, self.wan_port)
            else:
                key = utils.get_hash(self.buffers[flow][:block_size])
                if key in self.data.keys():
                    packet.payload = key
                    packet.is_raw_data = False
                    self.buffers[flow] = self.buffers[flow][block_size:]
                    self.send(packet, self.wan_port)
                else:
                    self.data[key] = self.buffers[flow][:block_size]
                    self.buffers[flow] = self.buffers[flow][block_size:]
                    packet.payload = self.data[key]
                    self.send_large(packet, self.wan_port)
