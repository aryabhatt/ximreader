import numpy as np
from pylinac.core.image import XIM
from ximreader import ximReader
from timeit import timeit

my_xim_file =  "Proj_00000.xim"
xim_img = XIM(my_xim_file)
img1 = xim_img.array
img2 = ximReader(my_xim_file)

# Check if the images are the same
err = np.linalg.norm(img1 - img2)/ np.linalg.norm(img1)
print("Reading error: {0}.".format(err))


# Time the reading
t1 = timeit(lambda: XIM(my_xim_file), number=20)
t2 = timeit(lambda: ximReader(my_xim_file), number=20)
print("ximRader is {0:.2f} times faster than pylinac.".format(t1/t2))
