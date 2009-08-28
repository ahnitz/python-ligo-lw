/*
*  Copyright (C) 2007 John Whelan
*
*  This program is free software; you can redistribute it and/or modify
*  it under the terms of the GNU General Public License as published by
*  the Free Software Foundation; either version 2 of the License, or
*  (at your option) any later version.
*
*  This program is distributed in the hope that it will be useful,
*  but WITHOUT ANY WARRANTY; without even the implied warranty of
*  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
*  GNU General Public License for more details.
*
*  You should have received a copy of the GNU General Public License
*  along with with program; see the file COPYING. If not, write to the
*  Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
*  MA  02111-1307  USA
*/

/******************************** <lalVerbatim file="CZeroPadAndFFTTestCV">
Author: UTB Relativity Group; contact whelan@phys.utb.edu
$Id$
********************************* </lalVerbatim> */

/********************************************************** <lalLaTeX>
\subsection{Program \texttt{CZeroPadAndFFTTest.c}}
\label{stochastic:ss:CZeroPadAndFFTTest.c}

Test suite for \texttt{LALCZeroPadAndFFT()}.

\subsubsection*{Usage}
\begin{verbatim}
./CZeroPadAndFFTTest
Options:
  -h             print usage message
  -q             quiet: run silently
  -v             verbose: print extra information
  -d level       set lalDebugLevel to level
  -i filename    read time series from file filename
  -o filename    print frequency series to file filename
  -n length      input series contains length points
  -m             measure plan
\end{verbatim}

\subsubsection*{Description}

This program tests the routine \texttt{LALCZeroPadAndFFT()}, which
zero-pads and Fourier transforms a complex time series of length $N$ to
produce a complex frequency series of length $2N-1$.

First, it tests that the correct error codes
(\textit{cf.}\ Sec.~\ref{stochastic:s:StochasticCrossCorrelation.h})
are generated for the following error conditions (tests in
\textit{italics} are not performed if \verb+LAL_NDEBUG+ is set, as
the corresponding checks in the code are made using the ASSERT macro):
\begin{itemize}
\item \textit{null pointer to output series}
\item \textit{null pointer to input series}
\item \textit{null pointer to parameter structure}
\item \textit{null pointer to FFT plan}
\item \textit{null pointer to data member of window function}
\item \textit{null pointer to data member of output series}
\item \textit{null pointer to data member of input series}
\item \textit{null pointer to data member of optimal filter}
\item \textit{null pointer to data member of data member of input series}
\item \textit{null pointer to data member of data member of output series}
\item \textit{zero length}
\item \textit{negative time spacing}
\item \textit{zero time spacing}
\item length mismatch between input series and window function
\item length mismatch between output series and zero-padded data
\item output series shorter than input series
\end{itemize}

It then verifies that the correct frequency series\footnote{The values
  are compared to a series generated by Matlab, correcting for the
  differing sign convention.} is generated for the simple test case
$\{h[k]=1+k|k=0,\ldots,7\}$ with $\delta t=0.5\,\textrm{s}$
and rectangular windowing.  For each
successful test (both of these valid data and the invalid ones
described above), it prints ``\texttt{PASS}'' to standard output; if a
test fails, it prints ``\texttt{FAIL}''.

If the \texttt{filename} arguments are present, it also reads a time
series from a file, calls \texttt{LALCZeroPadAndFFT()}, and writes the
results to the specified output file.

\subsubsection*{Exit codes}
\input{CZeroPadAndFFTTestCE}

\subsubsection*{Uses}
\begin{verbatim}
LALCZeroPadAndFFT()
LALCheckMemoryLeaks()
LALCReadTimeSeries()
LALCPrintFrequencySeries()
LALCCreateVector()
LALCDestroyVector()
LALCHARCreateVector()
LALCHARDestroyVector()
LALCreateForwardRealFFTPlan()
LALDestroyRealFFTPlan()
LALUnitAsString()
LALUnitCompare()
getopt()
printf()
fprintf()
freopen()
fabs()
\end{verbatim}

\subsubsection*{Notes}

\begin{itemize}
\item No specific error checking is done on user-specified data.  If
  \texttt{length} is missing, the resulting default will cause a bad
  data error.
\item The length of the user-provided series must be specified, even
  though it could in principle be deduced from the input file, because
  the data sequences must be allocated before the
  \texttt{LALCReadTimeSeries()} function is called.
\item If one \texttt{filename} argument, but not both, is present,
  the user-specified data will be silently ignored.
\end{itemize}

\vfill{\footnotesize\input{CZeroPadAndFFTTestCV}}

******************************************************* </lalLaTeX> */

#include <lal/LALStdlib.h>
#include <lal/Window.h>

#include <math.h>
#include <string.h>
#include <stdio.h>
#include <config.h>

#ifdef HAVE_UNISTD_H
#include <unistd.h>
#endif

#ifdef HAVE_GETOPT_H
#include <getopt.h>
#endif

#include <lal/StochasticCrossCorrelation.h>
#include <lal/AVFactories.h>
#include <lal/ReadFTSeries.h>
#include <lal/PrintFTSeries.h>
#include <lal/Units.h>

#include "CheckStatus.h"

NRCSID(CZEROPADANDFFTTESTC, "$Id$");

#define CZEROPADANDFFTTESTC_LENGTH        8
#define CZEROPADANDFFTTESTC_FULLLENGTH (2 * CZEROPADANDFFTTESTC_LENGTH - 1)
#define CZEROPADANDFFTTESTC_EPOCHSEC      1234
#define CZEROPADANDFFTTESTC_EPOCHNS       56789
#define CZEROPADANDFFTTESTC_DELTAT        0.5
#define CZEROPADANDFFTTESTC_DELTAF 1.0/(CZEROPADANDFFTTESTC_FULLLENGTH * CZEROPADANDFFTTESTC_DELTAT)
#define CZEROPADANDFFTTESTC_FBASE         10
#define CZEROPADANDFFTTESTC_FMIN  (CZEROPADANDFFTTESTC_FBASE - (CZEROPADANDFFTTESTC_LENGTH - 1) * CZEROPADANDFFTTESTC_DELTAF)
#define CZEROPADANDFFTTESTC_TOL           1e-6

#define CZEROPADANDFFTTESTC_TRUE     1
#define CZEROPADANDFFTTESTC_FALSE    0

extern char *optarg;
extern int   optind;

/* int lalDebugLevel = LALMSGLVL3; */
int lalDebugLevel  = LALNDEBUG;
BOOLEAN optVerbose = CZEROPADANDFFTTESTC_FALSE;
BOOLEAN optMeasurePlan = CZEROPADANDFFTTESTC_FALSE;
UINT4 optLength    = 0;


CHAR optInputFile[LALNameLength] = "";
CHAR optOutputFile[LALNameLength] = "";
INT4 code;

static void
Usage (const char *program, int exitflag);

static void
ParseOptions (int argc, char *argv[]);

/***************************** <lalErrTable file="CZeroPadAndFFTTestCE"> */
#define CZEROPADANDFFTTESTC_ENOM 0
#define CZEROPADANDFFTTESTC_EARG 1
#define CZEROPADANDFFTTESTC_ECHK 2
#define CZEROPADANDFFTTESTC_EFLS 3
#define CZEROPADANDFFTTESTC_EUSE 4

#define CZEROPADANDFFTTESTC_MSGENOM "Nominal exit"
#define CZEROPADANDFFTTESTC_MSGEARG "Error parsing command-line arguments"
#define CZEROPADANDFFTTESTC_MSGECHK "Error checking failed to catch bad data"
#define CZEROPADANDFFTTESTC_MSGEFLS "Incorrect answer for valid data"
#define CZEROPADANDFFTTESTC_MSGEUSE "Bad user-entered data"
/***************************** </lalErrTable> */

int
main( int argc, char *argv[] )
{

   static LALStatus         status;

   UINT4      i;
   REAL8      f;

   COMPLEX8                *cPtr;

   const COMPLEX8    testInputDataData[CZEROPADANDFFTTESTC_LENGTH]
     = {{1.0,0.0}, {2.0,0.0}, {3.0,0.0}, {4.0,0.0}, {5.0,0.0}, {6.0,0.0},
	{7.0,0.0}, {8.0,0.0}};

   COMPLEX8 expectedOutputDataData[CZEROPADANDFFTTESTC_FULLLENGTH]
     = { {+2.208174802380956e-01, +4.325962305777781e+00},
	 {+3.090169943749475e-01, -4.306254604896173e+00},
	 {+5.329070518200751e-15, +5.196152422706625e+00},
	 {+3.502214272222959e-01, -5.268737078678177e+00},
	 {-8.090169943749448e-01, +7.918722831227928e+00},
	 {+3.693524635113721e-01, -9.326003289238411e+00},
	 {-1.094039137097177e+01, +2.279368601990178e+01},
	 {+3.600000000000000e+01, 0.0},
	 {-1.094039137097177e+01, -2.279368601990178e+01},
	 {+3.693524635113721e-01, +9.326003289238411e+00},
	 {-8.090169943749448e-01, -7.918722831227928e+00},
	 {+3.502214272222959e-01, +5.268737078678177e+00},
	 {+5.329070518200751e-15, -5.196152422706625e+00},
	 {+3.090169943749475e-01, +4.306254604896173e+00},
	 {+2.208174802380956e-01, -4.325962305777781e+00} };

   COMPLEX8TimeSeries             goodInput, badInput;
   COMPLEX8FrequencySeries        goodOutput, badOutput;

   BOOLEAN                result;
   LALUnitPair            unitPair;
   LALUnit                expectedUnit;
   CHARVector             *unitString;

   CZeroPadAndFFTParameters   goodParams, badParams;
   LALWindowParams    windowParams;

   goodParams.window = NULL;
   goodParams.fftPlan = NULL;
   goodParams.length = CZEROPADANDFFTTESTC_FULLLENGTH;

   windowParams.length = CZEROPADANDFFTTESTC_LENGTH;
   windowParams.type = Rectangular;

   /* build window */
   LALSCreateVector(&status, &(goodParams.window), CZEROPADANDFFTTESTC_LENGTH);
   if ( ( code = CheckStatus( &status, 0 , "",
			      CZEROPADANDFFTTESTC_EFLS,
			      CZEROPADANDFFTTESTC_MSGEFLS ) ) )
   {
     return code;
   }

   LALWindow(&status, goodParams.window, &windowParams);
   if ( ( code = CheckStatus( &status, 0 , "",
			      CZEROPADANDFFTTESTC_EFLS,
			      CZEROPADANDFFTTESTC_MSGEFLS ) ) )
   {
     return code;
   }

   badParams = goodParams;

   /* Fill in expected output */

   for (i=0; i<CZEROPADANDFFTTESTC_FULLLENGTH; ++i)
   {
     expectedOutputDataData[i].re *= CZEROPADANDFFTTESTC_DELTAT;
     expectedOutputDataData[i].im *= CZEROPADANDFFTTESTC_DELTAT;
   }

   ParseOptions( argc, argv );

   /* TEST INVALID DATA HERE ------------------------------------------- */

   /* define valid parameters */
   goodInput.f0                   = CZEROPADANDFFTTESTC_FBASE;
   goodInput.deltaT               = CZEROPADANDFFTTESTC_DELTAT;
   goodInput.epoch.gpsSeconds     = CZEROPADANDFFTTESTC_EPOCHSEC;
   goodInput.epoch.gpsNanoSeconds = CZEROPADANDFFTTESTC_EPOCHNS;
   goodInput.data                 = NULL;
   goodOutput.data                = NULL;

   badInput = goodInput;
   badOutput = goodOutput;

   /* construct plan */
   LALCreateForwardComplexFFTPlan(&status, &(goodParams.fftPlan),
				  CZEROPADANDFFTTESTC_FULLLENGTH,
				  CZEROPADANDFFTTESTC_FALSE);
   if ( ( code = CheckStatus( &status, 0 , "",
			      CZEROPADANDFFTTESTC_EFLS,
			      CZEROPADANDFFTTESTC_MSGEFLS ) ) )
   {
     return code;
   }
   /* allocate input and output vectors */
   LALCCreateVector(&status, &(goodInput.data), CZEROPADANDFFTTESTC_LENGTH);
   if ( ( code = CheckStatus( &status, 0 , "",
			      CZEROPADANDFFTTESTC_EFLS,
			      CZEROPADANDFFTTESTC_MSGEFLS ) ) )
   {
     return code;
   }
   LALCCreateVector(&status, &(goodOutput.data),
		    CZEROPADANDFFTTESTC_FULLLENGTH);
   if ( ( code = CheckStatus( &status, 0 , "",
			      CZEROPADANDFFTTESTC_EFLS,
			      CZEROPADANDFFTTESTC_MSGEFLS ) ) )
   {
     return code;
   }

#ifndef LAL_NDEBUG
   if ( ! lalNoDebug )
   {
     /* test behavior for null pointer to output series */
     LALCZeroPadAndFFT(&status, NULL, &goodInput, &goodParams);
     if ( ( code = CheckStatus(&status, STOCHASTICCROSSCORRELATIONH_ENULLPTR,
			       STOCHASTICCROSSCORRELATIONH_MSGENULLPTR,
			       CZEROPADANDFFTTESTC_ECHK,
			       CZEROPADANDFFTTESTC_MSGECHK ) ) )
     {
       return code;
     }
     printf("  PASS: null pointer to output series results in error:\n       \"%s\"\n", STOCHASTICCROSSCORRELATIONH_MSGENULLPTR);

     /* test behavior for null pointer to input series */
     LALCZeroPadAndFFT(&status, &goodOutput, NULL, &goodParams);
     if ( ( code = CheckStatus(&status, STOCHASTICCROSSCORRELATIONH_ENULLPTR,
			       STOCHASTICCROSSCORRELATIONH_MSGENULLPTR,
			       CZEROPADANDFFTTESTC_ECHK,
			       CZEROPADANDFFTTESTC_MSGECHK ) ) )
     {
       return code;
     }
     printf("  PASS: null pointer to input series results in error:\n       \"%s\"\n", STOCHASTICCROSSCORRELATIONH_MSGENULLPTR);

     /* test behavior for null pointer to parameter structure */
     LALCZeroPadAndFFT(&status, &goodOutput, &goodInput, NULL);
     if ( ( code = CheckStatus( &status, STOCHASTICCROSSCORRELATIONH_ENULLPTR,
				STOCHASTICCROSSCORRELATIONH_MSGENULLPTR,
				CZEROPADANDFFTTESTC_ECHK,
				CZEROPADANDFFTTESTC_MSGECHK ) ) )
     {
       return code;
     }
     printf("  PASS: null pointer to parameter structure results in error:\n       \"%s\"\n", STOCHASTICCROSSCORRELATIONH_MSGENULLPTR);

     /* test behavior for null pointer to FFT plan */
     badParams.fftPlan = NULL;
     LALCZeroPadAndFFT(&status, &goodOutput, &goodInput, &badParams);
     if ( ( code = CheckStatus( &status, STOCHASTICCROSSCORRELATIONH_ENULLPTR,
				STOCHASTICCROSSCORRELATIONH_MSGENULLPTR,
				CZEROPADANDFFTTESTC_ECHK,
				CZEROPADANDFFTTESTC_MSGECHK ) ) )
     {
       return code;
     }
     printf("  PASS: null pointer to FFT plan results in error:\n       \"%s\"\n", STOCHASTICCROSSCORRELATIONH_MSGENULLPTR);
     badParams.fftPlan = goodParams.fftPlan;

     /* test behavior for null pointer to data member of output series */
     LALCZeroPadAndFFT(&status, &badOutput, &goodInput, &goodParams);
     if ( ( code = CheckStatus(&status, STOCHASTICCROSSCORRELATIONH_ENULLPTR,
			       STOCHASTICCROSSCORRELATIONH_MSGENULLPTR,
			       CZEROPADANDFFTTESTC_ECHK,
			       CZEROPADANDFFTTESTC_MSGECHK ) ) )
     {
       return code;
     }
     printf("  PASS: null pointer to data member of output series results in error:\n       \"%s\"\n", STOCHASTICCROSSCORRELATIONH_MSGENULLPTR);

     /* test behavior for null pointer to data member of input series */
     LALCZeroPadAndFFT(&status, &goodOutput, &badInput, &goodParams);
     if ( ( code = CheckStatus(&status, STOCHASTICCROSSCORRELATIONH_ENULLPTR,
			       STOCHASTICCROSSCORRELATIONH_MSGENULLPTR,
			       CZEROPADANDFFTTESTC_ECHK,
			       CZEROPADANDFFTTESTC_MSGECHK ) ) )
     {
       return code;
     }
     printf("  PASS: null pointer to data member of input series results in error:\n       \"%s\"\n", STOCHASTICCROSSCORRELATIONH_MSGENULLPTR);

     /* test behavior for null pointer to data member of data member of output series */
     LALCCreateVector(&status, &(badOutput.data),
		      CZEROPADANDFFTTESTC_FULLLENGTH);
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }
     cPtr = badOutput.data->data;
     badOutput.data->data = NULL;
     LALCZeroPadAndFFT(&status, &badOutput, &goodInput, &goodParams);
     if ( ( code = CheckStatus(&status, STOCHASTICCROSSCORRELATIONH_ENULLPTR,
			       STOCHASTICCROSSCORRELATIONH_MSGENULLPTR,
			       CZEROPADANDFFTTESTC_ECHK,
			       CZEROPADANDFFTTESTC_MSGECHK ) ) )
     {
       return code;
     }
     printf("  PASS: null pointer to data member of data member of output series results in error:\n       \"%s\"\n", STOCHASTICCROSSCORRELATIONH_MSGENULLPTR);
     badOutput.data->data = cPtr;
     LALCDestroyVector(&status, &(badOutput.data));
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }

     /* test behavior for null pointer to data member of data member of output series */
     LALCCreateVector(&status, &(badInput.data), CZEROPADANDFFTTESTC_LENGTH);
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }
     cPtr = badInput.data->data;
     badInput.data->data = NULL;
     LALCZeroPadAndFFT(&status, &goodOutput, &badInput, &goodParams);
     if ( ( code = CheckStatus(&status, STOCHASTICCROSSCORRELATIONH_ENULLPTR,
			       STOCHASTICCROSSCORRELATIONH_MSGENULLPTR,
			       CZEROPADANDFFTTESTC_ECHK,
			       CZEROPADANDFFTTESTC_MSGECHK ) ) )
     {
       return code;
     }
     printf("  PASS: null pointer to data member of data member of input series results in error:\n       \"%s\"\n", STOCHASTICCROSSCORRELATIONH_MSGENULLPTR);
     badInput.data->data = cPtr;
     LALCDestroyVector(&status, &(badInput.data));
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }

     /* test behavior for zero length */
     goodInput.data->length = goodOutput.data->length = 0;
     /* plan->size = -1; */
     LALCZeroPadAndFFT(&status, &goodOutput, &goodInput, &goodParams);
     if ( ( code = CheckStatus(&status, STOCHASTICCROSSCORRELATIONH_EZEROLEN,
			       STOCHASTICCROSSCORRELATIONH_MSGEZEROLEN,
			       CZEROPADANDFFTTESTC_ECHK,
			       CZEROPADANDFFTTESTC_MSGECHK) ) )
     {
       return code;
     }
     printf("  PASS: zero length results in error:\n       \"%s\"\n",
            STOCHASTICCROSSCORRELATIONH_MSGEZEROLEN);
     /* reassign valid length */
     goodInput.data->length   = CZEROPADANDFFTTESTC_LENGTH;
     goodOutput.data->length  = CZEROPADANDFFTTESTC_FULLLENGTH;

     /* plan->size = CZEROPADANDFFTTESTC_FULLLENGTH; */

     /* test behavior for negative time spacing */
     goodInput.deltaT = -CZEROPADANDFFTTESTC_DELTAT;
     LALCZeroPadAndFFT(&status, &goodOutput, &goodInput, &goodParams);
     if ( ( code = CheckStatus(&status,
			       STOCHASTICCROSSCORRELATIONH_ENONPOSDELTAT,
			       STOCHASTICCROSSCORRELATIONH_MSGENONPOSDELTAT,
			       CZEROPADANDFFTTESTC_ECHK,
			       CZEROPADANDFFTTESTC_MSGECHK) ) )
     {
       return code;
     }
     printf("  PASS: negative time spacing results in error:\n       \"%s\"\n",
            STOCHASTICCROSSCORRELATIONH_MSGENONPOSDELTAT);

     /* test behavior for zero time spacing */
     goodInput.deltaT = 0;
     LALCZeroPadAndFFT(&status, &goodOutput, &goodInput, &goodParams);
     if ( ( code = CheckStatus(&status,
			       STOCHASTICCROSSCORRELATIONH_ENONPOSDELTAT,
			       STOCHASTICCROSSCORRELATIONH_MSGENONPOSDELTAT,
			       CZEROPADANDFFTTESTC_ECHK,
			       CZEROPADANDFFTTESTC_MSGECHK) ) )
     {
       return code;
     }
     printf("  PASS: zero time spacing results in error:\n       \"%s\"\n",
            STOCHASTICCROSSCORRELATIONH_MSGENONPOSDELTAT);
     /* reassign valid time spacing */
     goodInput.deltaT = CZEROPADANDFFTTESTC_DELTAT;

   } /* if ( ! lalNoDebug ) */
#endif /* NDEBUG */

   /* test behavior for length mismatch between input series and output series */
   goodOutput.data->length = CZEROPADANDFFTTESTC_LENGTH;
   LALCZeroPadAndFFT(&status, &goodOutput, &goodInput, &goodParams);
   if ( ( code = CheckStatus(&status,
			     STOCHASTICCROSSCORRELATIONH_EMMLEN,
			     STOCHASTICCROSSCORRELATIONH_MSGEMMLEN,
			     CZEROPADANDFFTTESTC_ECHK,
			     CZEROPADANDFFTTESTC_MSGECHK) ) )
   {
     return code;
   }
   printf("  PASS: length mismatch between input series and output series results in error:\n       \"%s\"\n",
          STOCHASTICCROSSCORRELATIONH_MSGEMMLEN);
   goodOutput.data->length = CZEROPADANDFFTTESTC_FULLLENGTH;

   /* TEST VALID DATA HERE --------------------------------------------- */

   /* fill input time-series parameters */
   strncpy(goodInput.name,"Dummy test data",LALNameLength);
   goodInput.sampleUnits  = lalDimensionlessUnit;
   goodInput.sampleUnits.unitNumerator[LALUnitIndexADCCount] = 1;

     /* fill input time-series data */
   for (i=0; i<CZEROPADANDFFTTESTC_LENGTH; ++i)
   {
     goodInput.data->data[i] = testInputDataData[i];
   }

   /* zero-pad and FFT */
   LALCZeroPadAndFFT(&status, &goodOutput, &goodInput, &goodParams);
   if ( ( code = CheckStatus( &status, 0 , "",
			    CZEROPADANDFFTTESTC_EFLS,
			      CZEROPADANDFFTTESTC_MSGEFLS) ) )
   {
     return code;
   }

   /* check output f0 */
   if (optVerbose)
   {
     printf("f0=%g, should be %g\n", goodOutput.f0,
	    CZEROPADANDFFTTESTC_FMIN);
   }
   if (goodOutput.f0 != CZEROPADANDFFTTESTC_FMIN)
   {
     printf("  FAIL: Valid data test\n");
     if (optVerbose)
     {
       printf("Exiting with error: %s\n", CZEROPADANDFFTTESTC_MSGEFLS);
     }
     return CZEROPADANDFFTTESTC_EFLS;
   }

   /* check output deltaF */
   if (optVerbose)
   {
     printf("deltaF=%g, should be %g\n", goodOutput.deltaF,
            CZEROPADANDFFTTESTC_DELTAF);
   }
   if ( fabs(goodOutput.deltaF-CZEROPADANDFFTTESTC_DELTAF)
        / CZEROPADANDFFTTESTC_DELTAF > CZEROPADANDFFTTESTC_TOL )
   {
     printf("  FAIL: Valid data test\n");
     if (optVerbose)
     {
       printf("Exiting with error: %s\n", CZEROPADANDFFTTESTC_MSGEFLS);
     }
     return CZEROPADANDFFTTESTC_EFLS;
   }

   /* check output epoch */
   if (optVerbose)
   {
     printf("epoch=%d seconds, %d nanoseconds; should be %d seconds, %d nanoseconds\n",
            goodOutput.epoch.gpsSeconds, goodOutput.epoch.gpsNanoSeconds,
            CZEROPADANDFFTTESTC_EPOCHSEC, CZEROPADANDFFTTESTC_EPOCHNS);
   }
   if ( goodOutput.epoch.gpsSeconds != CZEROPADANDFFTTESTC_EPOCHSEC
        || goodOutput.epoch.gpsNanoSeconds != CZEROPADANDFFTTESTC_EPOCHNS )
   {
     printf("  FAIL: Valid data test\n");
     if (optVerbose)
     {
       printf("Exiting with error: %s\n", CZEROPADANDFFTTESTC_MSGEFLS);
     }
     return CZEROPADANDFFTTESTC_EFLS;
   }

   /* check output units */
   expectedUnit = lalDimensionlessUnit;
   expectedUnit.unitNumerator[LALUnitIndexADCCount] = 1;
   expectedUnit.unitNumerator[LALUnitIndexSecond] = 1;
   unitPair.unitOne = &expectedUnit;
   unitPair.unitTwo = &(goodOutput.sampleUnits);
   LALUnitCompare(&status, &result, &unitPair);
   if ( ( code = CheckStatus( &status, 0 , "",
			      CZEROPADANDFFTTESTC_EFLS,
			      CZEROPADANDFFTTESTC_MSGEFLS ) ) )
   {
     return code;
   }

   if (optVerbose)
   {
     unitString = NULL;
     LALCHARCreateVector(&status, &unitString, LALUnitTextSize);
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }

     LALUnitAsString( &status, unitString, unitPair.unitTwo );
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }
     printf( "Units are \"%s\", ", unitString->data );

     LALUnitAsString( &status, unitString, unitPair.unitOne );
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }
     printf( "should be \"%s\"\n", unitString->data );

     LALCHARDestroyVector(&status, &unitString);
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }
   }

   if (!result)
   {
     printf("  FAIL: Valid data test #1\n");
     if (optVerbose)
     {
       printf("Exiting with error: %s\n",
              CZEROPADANDFFTTESTC_MSGEFLS);
     }
     return CZEROPADANDFFTTESTC_EFLS;
   }

   /* check output values */

   for (i=1; i<CZEROPADANDFFTTESTC_FULLLENGTH; ++i)
   {
     f = CZEROPADANDFFTTESTC_FMIN + i * CZEROPADANDFFTTESTC_DELTAF;
     if (optVerbose)
     {
       printf("hBarTilde(%f Hz)=%g + %g i, should be %g + %g i\n",
              f, goodOutput.data->data[i].re, goodOutput.data->data[i].im,
              expectedOutputDataData[i].re, expectedOutputDataData[i].im);
     }
     if (fabs(goodOutput.data->data[i].re - expectedOutputDataData[i].re)
         /* / expectedOutputDataData[0].re */> CZEROPADANDFFTTESTC_TOL
         || fabs(goodOutput.data->data[i].im - expectedOutputDataData[i].im)
         /* / expectedOutputDataData[0].re */> CZEROPADANDFFTTESTC_TOL)
     {
       printf("  FAIL: Valid data test\n");
       if (optVerbose)
       {
         printf("Exiting with error: %s\n", CZEROPADANDFFTTESTC_MSGEFLS);
       }
       return CZEROPADANDFFTTESTC_EFLS;
     }
   }

    /* write results to output file
   LALSPrintTimeSeries(&input, "zeropadgoodInput.dat");
   LALCPrintFrequencySeries(&output, "zeropadgoodOutput.dat");*/

   /* clean up valid data */
   LALCDestroyVector(&status, &goodInput.data);
   if ( ( code = CheckStatus(&status, 0 , "",
			     CZEROPADANDFFTTESTC_EFLS,
			     CZEROPADANDFFTTESTC_MSGEFLS) ) )
   {
     return code;
   }
   LALCDestroyVector(&status, &goodOutput.data);
   if ( ( code = CheckStatus(&status, 0 , "",
			     CZEROPADANDFFTTESTC_EFLS,
			     CZEROPADANDFFTTESTC_MSGEFLS) ) )
   {
     return code;
   }
   LALDestroyComplexFFTPlan(&status, &(goodParams.fftPlan));
   if ( ( code = CheckStatus(&status, 0 , "",
			     CZEROPADANDFFTTESTC_EFLS,
			     CZEROPADANDFFTTESTC_MSGEFLS) ) )
   {
     return code;
   }
   LALSDestroyVector(&status, &(goodParams.window));
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
   {
     return code;
   }

   LALCheckMemoryLeaks();

   printf("PASS: all tests\n");

   /**************** Process User-Entered Data, If Any **************/

   if (optInputFile[0] && optOutputFile[0]){
     /* construct plan*/
     LALCreateForwardComplexFFTPlan(&status, &(goodParams.fftPlan), 2*optLength - 1,
				   optMeasurePlan);
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }

     goodInput.data  = NULL;
     goodOutput.data = NULL;

     LALCCreateVector(&status, &goodInput.data, optLength);
     if ( ( code = CheckStatus( &status, 0 , "",
				CZEROPADANDFFTTESTC_EUSE,
				CZEROPADANDFFTTESTC_MSGEUSE) ) )
     {
       return code;
     }
     LALCCreateVector(&status, &goodOutput.data,  2*optLength - 1);
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }

     /* Read input file */
     LALCReadTimeSeries(&status, &goodInput, optInputFile);
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }

     /* calculate zero-pad and FFT */
     LALCZeroPadAndFFT(&status, &goodOutput, &goodInput, &goodParams);
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }

     LALCPrintFrequencySeries(&goodOutput, optOutputFile);

     printf("===== FFT of Zero-Padded User-Specified Data Written to File %s =====\n", optOutputFile);

     /* clean up valid data */
     LALCDestroyVector(&status, &goodInput.data);
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }
     LALCDestroyVector(&status, &goodOutput.data);
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }
     LALDestroyComplexFFTPlan(&status, &(goodParams.fftPlan));
     if ( ( code = CheckStatus(&status, 0 , "",
			       CZEROPADANDFFTTESTC_EFLS,
			       CZEROPADANDFFTTESTC_MSGEFLS) ) )
     {
       return code;
     }
     LALCheckMemoryLeaks();
   }
   return CZEROPADANDFFTTESTC_ENOM;
}

/*------------------------------------------------------------------------*/

/*
 * Usage ()
 *
 * Prints a usage message for program program and exits with code exitcode.
 *
 */
static void
Usage (const char *program, int exitcode)
{
  fprintf (stderr, "Usage: %s [options]\n", program);
  fprintf (stderr, "Options:\n");
  fprintf (stderr, "  -h             print this message\n");
  fprintf (stderr, "  -q             quiet: run silently\n");
  fprintf (stderr, "  -v             verbose: print extra information\n");
  fprintf (stderr, "  -d level       set lalDebugLevel to level\n");
  fprintf (stderr, "  -i filename    read time series from file filename\n");
  fprintf (stderr, "  -o filename    print frequency series to file filename\n");
  fprintf (stderr, "  -n length      input series contains length points\n");
  fprintf (stderr, "  -m             measure plan\n");
  exit (exitcode);
}


/*
 * ParseOptions ()
 *
 * Parses the argc - 1 option strings in argv[].
 *
 */
static void
ParseOptions (int argc, char *argv[])
{
  while (1)
  {
    int c = -1;

    c = getopt (argc, argv, "hqvd:i:o:n:m");
    if (c == -1)
    {
      break;
    }

    switch (c)
    {
      case 'i': /* specify input file */
        strncpy (optInputFile, optarg, LALNameLength);
        break;

      case 'o': /* specify output file */
        strncpy (optOutputFile, optarg, LALNameLength);
        break;

      case 'n': /* specify number of points in series */
        optLength = atoi (optarg);
        break;

      case 'm': /* specify whether or not to measure plan */
        optMeasurePlan = CZEROPADANDFFTTESTC_TRUE;
        break;

      case 'd': /* set debug level */
        lalDebugLevel = atoi (optarg);
        break;

      case 'v': /* optVerbose */
        optVerbose = CZEROPADANDFFTTESTC_TRUE;
        break;

      case 'q': /* quiet: run silently (ignore error messages) */
        freopen ("/dev/null", "w", stderr);
        freopen ("/dev/null", "w", stdout);
        break;

      case 'h':
        Usage (argv[0], 0);
        break;


      default:
        Usage (argv[0], 1);
    }

  }

  if (optind < argc)
  {
    Usage (argv[0], 1);
  }

  return;
}