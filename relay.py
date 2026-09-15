"""Host the Rally controller on the friend's machine; connect through SSH."""
import argparse
import json
import rally
from remote import RelayServer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', required=True, choices=['model', 'rtl', 'serial'])
    parser.add_argument('--port', help='USB-UART device on this machine, required for serial')
    parser.add_argument('--tcp-port', type=int, default=4768, help='local TCP port; 0 selects an available port')
    args = parser.parse_args()
    if not 0 <= args.tcp_port <= 65535:
        parser.error('--tcp-port must be between 0 and 65535')
    if args.backend == 'serial' and not args.port:
        parser.error('--port is required for the serial backend')
    backend = {'model': rally.ModelBackend, 'rtl': rally.RTLBackend,
               'serial': lambda: rally.SerialBackend(args.port)}[args.backend]()
    try:
        with RelayServer(('127.0.0.1', args.tcp_port), backend, args.backend) as server:
            print(json.dumps({'listen': '127.0.0.1', 'port': server.server_address[1],
                              'backend': args.backend, 'single_client': True}), flush=True)
            try:
                server.serve_forever(poll_interval=.1)
            except KeyboardInterrupt:
                pass
    finally:
        backend.close()


if __name__ == '__main__':
    main()
