#!/usr/bin/env python
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#           http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Delete snapshots in the metaopenstack that manages the servers.

Use this if you have `management.type` set to `metaopenstack` in the
configuration to get rid of the snapshot images of the servers.
If only part of them exists, it will delete them anyway and exit successfully.
"""

import logging
import destroystack.tools.state_restoration.metaopenstack as metaopenstack

logging.basicConfig(level=logging.INFO)


def main():
    metaopenstack.delete_snapshots()


if __name__ == '__main__':
    main()
