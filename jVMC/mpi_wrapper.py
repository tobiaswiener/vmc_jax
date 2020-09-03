from mpi4py import MPI
import jax
import jax.numpy as jnp
import numpy as np

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
commSize = comm.Get_size()

globNumSamples=0
myNumSamples=0

from functools import partial

@partial(jax.pmap, axis_name='i')
def _sum_up_pmapd(data):
    s = jnp.sum(data, axis=0)
    return jax.lax.psum(s, 'i')

@partial(jax.pmap, axis_name='i', in_axes=(0,None))
def _sum_sq_pmapd(data,mean):
    s = jnp.linalg.norm(data - mean, axis=0)**2
    return jax.lax.psum(s, 'i')


def distribute_sampling(numSamples, localDevices=None, numChainsPerDevice=1):

    global globNumSamples
    
    if localDevices is None:
    
        globNumSamples = numSamples

        mySamples = numSamples // commSize

        if rank < numSamples % commSize:
            mySamples+=1

        return mySamples

    mySamples = numSamples // commSize

    if rank < numSamples % commSize:
        mySamples+=1

    mySamples = (mySamples + localDevices - 1) // localDevices
    mySamples = (mySamples + numChainsPerDevice - 1) // numChainsPerDevice

    globNumSamples = commSize * localDevices * numChainsPerDevice * mySamples

    return mySamples


def first_sample_id():

    global globNumSamples

    mySamples = globNumSamples // commSize

    firstSampleId = rank * mySamples

    if rank < globNumSamples % commSize:
        firstSampleId += rank
    else:
        firstSampleId += globNumSamples % commSize

    return firstSampleId


def global_sum(data):

    # Compute sum locally
    localSum = np.array( _sum_up_pmapd(data)[0] )
    
    # Allocate memory for result
    res = np.empty_like(localSum, dtype=localSum.dtype)

    # Global sum
    comm.Allreduce(localSum, res, op=MPI.SUM)

    return jnp.array(res)


def global_mean(data):

    global globNumSamples

    return global_sum(data) / globNumSamples


def global_variance(data):

    mean = global_mean(data)

    # Compute sum locally
    localSum = np.array( _sum_sq_pmapd(data,mean) )
    
    # Allocate memory for result
    res = np.empty_like(localSum, dtype=localSum.dtype)

    # Global sum
    global globNumSamples
    comm.Allreduce(localSum, res, op=MPI.SUM)

    return jnp.array(res) / globNumSamples



if __name__ == "__main__":
    data=jnp.array(np.arange(720*4).reshape((720,4)))
    myNumSamples = distribute_sampling(720)
    
    myData=data[rank*myNumSamples:(rank+1)*myNumSamples]

    print(global_mean(myData)-jnp.mean(data,axis=0))