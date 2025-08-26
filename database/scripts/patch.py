import sys, pathlib
import chromadb
import json
import base64
from collections import defaultdict
from tqdm import tqdm
from typing import Union
from logging import getLogger

logger = getLogger(__name__)
sys.path.append(pathlib.Path(__file__).parents[2].as_posix())

from utils import functions, get_database, get_model, settings, metadata

textdb = get_database.get_database("textdb")

Q1 = """What should be recorded for the power distribution panel under 30-day check?
• Record the +48V output voltage and current from the LCD Display 
• Record the -48V output voltage and current from the LCD Display 
• Record the +24V output voltage and current from the LCD Display 
• Record the 415VAC input voltage and current from the LCD Display 
• Record the battery current from the LCD Display"""

Q2 = """How to update the DCU software?
Download New Version DCU Software
Procedures:
1. Connect yellow PTE cable to DCU
2. Connect the yellow PTE cable to the computer, using an optical bridge if necessary
3. Start Terminal Software
4. Select File/Open/Kaba.TRM
5. Press space bar
6. Press “S” (start of download menu)
7. Press “D” (download start)
8. Select Transfers/Send Text file/Logik~1.txt (Make sure you have selected the correct version of software). Wait until Software is downloaded.
9. Reset power by switching the DCU off and back on
10. Press space bar
11. Press “T” (transparent logic)
12. Press “D” (send download)
13. Wait for 10 seconds
14. Press “T” (transparent mode)
15. Select Transfers/Send Text file/Drive~1.txt (Make sure you have selected the correct version of software). Wait until Software is downloaded.
16. Reset power by switching the DCU off and back on
17. Close Terminal file
18. Open PTE file
19. Connect red PTE cable to the DCU
20. Select user DChan OR log-in with your user name if any
21. Check that the device setup shows the correct door and platform, if not correct the information and the click OK
22. Select Task/Default parameter
23. Select “Action”
24. Wait until DCU disconnected
25. Select “connect” again
26. An icon will pop up indicating the door location, if this is correct press OK
27. Overwrite confirmation is required, select OK
28. Select “Identification/Statistics” page, and control the actual SW Version. LOGIC: Software version, DRIVE: SW nr of Drive
29. Select Settings Page, click on the last item (Motor Type) second column and a (√) should appear, in the third column enter 1 (BML_10), press return
30. Press confirm
31. Select Task/New Setup and then Action
32. Switch the DCU local panel to “Test” position
33. Using the local control panel, open the door and hold the open position until there is a clicking sound (the doors should open slowly)
34. When the open door command is released the door should automatically close (the door should close in normal speed, if not, please re-do default parameter again)
35. Check visually that the doors have an extra closing force after the doors appear to be shut
36. Re-open the doors locally and test that the doors open at the correct speed and hold the doors open until a clicking sound is heard
37. Allow the doors to close and visually check for the extra closing force when the doors appear to be closed
38. Re-open the doors and when the doors are closing check that if an object (e.g. arm) is placed in the path of the doors, that they cease trying to close and re-open slightly. Remove the obstruction and verify that after a short time span the doors automatically close
39. If the doors operate correctly, repeat steps 34 and 35 ten to twelve times to confirm that the new software works properly
40. If the doors do not operate correctly or stop moving, reset the power by switching the DCU off and back on and then repeating steps 4 to 41
41. If the doors still do not work properly after downloading the new software, repeat steps 4-but loading with the old DCU Logic and Drive software, the door should resume normal operation, take a note of the door location/ door number and inform maintenance."""


Q3 = """Which items shall be visually inspected under 30-day check?
Items to be checked: PSD / EPSD / CAD / TAD: 
Visual inspection for any physical damage on Gasket, Brush, Sealing, Kickplate and Glass door panels"""


Q4 = """What is a DCU-Box?
The DCU-Box contains circuit breakers for the main power and printed circuit boards for control and drive. Two test switches allow manual operation for each single PSD. All electrical connections are plugged, except for the main power +/- 48VDC.
The DCU-Box is further equipped with an interface to the PTE for local observation or software download. The DCU controls the motor movement and speed, the solenoid in the locking block and keeps track of the sliding panel position by an encoder in the motor. Obstacle detection, edge/gap hazard detection and DOI are also connected to and controlled by the DCU. A CAN BUS-Connection (RS485) to the PSDC in the PSD Equipment Room enables the exchange of various signals for indication and Error Log. All safety relevant signals and commands are hard wired."""

Qs = [Q1, Q2, Q3, Q4]

# Insert Q1~Q4 directly into the database
# textdb.add(
#     documents=Qs,
#     metadatas=[
#         {
#             "type": "text",
#             "path": "",
#             "summary": q,
#             "page_idx": 41
#         }
#         for q in Qs
#     ], # type: ignore
#     ids=["Q1", "Q2", "Q3", "Q4"],
# )
results = textdb.query(
    query_texts=[Q1],
    n_results=5,
    include=["documents", "metadatas"],
)

for i in range(len(results["documents"][0])):
    print(results["documents"][0][i])
    print(results["metadatas"][0][i])
    print(results["ids"][0][i])
    print("=" * 80)


# NOTE - modified chunks for Q2
# textdb.delete(ids=["text_155_0", "text_155_1"])
