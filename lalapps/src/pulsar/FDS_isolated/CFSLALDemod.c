/* LALDemod variants put out of ComputeFStatistic.c for separate compilation
 * Authors see ComputeFStatistic.c
                                                         Bernd Machenschalk */
#include "ComputeFStatistic.h"

#if defined(USE_BOINC) && defined(_WIN32)
#include "win_lib.h"
#endif

/* this is defined in C99 and *should* be in math.h.  Long term
   protect this with a HAVE_FINITE */
int finite(double);

/* global variables defined in ComputeFStatistic.c */
extern INT4 cfsRunNo;	   /**< CFS run-number: 0=run only once, 1=first run, 2=second run */
extern UINT4 maxSFTindex;  /**< maximal sftindex, for error-checking */

#define LD_SMALL        (1.0e-9 / LAL_TWOPI)
#define OOTWOPI         (1.0 / LAL_TWOPI)
#ifndef LUT_RES
#define LUT_RES         64      /* resolution of lookup-table */
#endif

#define TWOPI_FLOAT     6.28318530717958f  /* 2*pi */
#define OOTWOPI_FLOAT   (1.0f / TWOPI_FLOAT)	/* 1 / (2pi) */ 


/* in case of the (now almost obsolete) hand-coded AltiVec version (and and experimental hook),
   don't use TestLALDemod() below, but the one in external file */
#if defined(USE_AKOS_MARKS)
#include "CFSLALDemod_Akos.c"
#elif defined(USE_EXP_LALDEMOD)
#include "CFSLALDemod_Experimental.c"
#else /* rather generic version */

RCSID( "$Id$");

/* <lalVerbatim file="LALDemodCP"> */
void TestLALDemod(LALStatus *status, LALFstat *Fs, FFT **input, DemodPar *params) 
/* </lalVerbatim> */
{ 

  INT4 alpha,i;                 /* loop indices */
  REAL8 *xSum=NULL, *ySum=NULL; /* temp variables for computation of fs*as and fs*bs */
  INT4 s;                       /* local variable for spinDwn calcs. */
  REAL8 xTemp;                  /* temp variable for phase model */
  REAL4 xTInt;                   /* integer part of xTemp */
  REAL8 deltaF;                 /* width of SFT band */
  /* INT4  k1;                     /* defining the sum over which is calculated */
  UINT4 k=0;
  REAL8 *skyConst;              /* vector of sky constants data */
  REAL8 *spinDwn;               /* vector of spinDwn parameters (maybe a structure? */
  INT4  spOrder;                /* maximum spinDwn order */
  REAL8 realXP, imagXP;         /* temp variables used in computation of */
  INT4  nDeltaF;                /* number of frequency bins per SFT band */
  INT4  sftIndex;               /* more temp variables */
  REAL8 realQ, imagQ;
  INT4 *tempInt1;
  /* UINT4 index; */
  REAL8 FaSq;
  REAL8 FbSq;
  REAL8 FaFb;
  COMPLEX16 Fa, Fb;
#ifdef USE_BOINC
#define klim 32
#else
  UINT4 klim = 2*params->Dterms;
#endif
  REAL8 f;
  static REAL8 sinVal[LUT_RES+(LUT_RES/4)+1]; /* Lookup tables for fast sin/cos calculation */
  static REAL8 *cosVal;

  static REAL8 sinVal2PI[LUT_RES+(LUT_RES/4)+1];
  static REAL8 sinVal2PIPI[LUT_RES+(LUT_RES/4)+1];
  static REAL8 *cosVal2PI, *cosVal2PIPI;
  static REAL8 divLUTtab[LUT_RES+1];
  static BOOLEAN firstCall = 1;

  REAL8 A=params->amcoe->A;
  REAL8 B=params->amcoe->B;
  REAL8 C=params->amcoe->C;
  REAL8 D=params->amcoe->D;

  UINT4 M=params->SFTno;

  INITSTATUS( status, "TestLALDemod", rcsid );

  /* catch some obvious programming errors */
  ASSERT ( (Fs != NULL)&&(Fs->F != NULL), status, COMPUTEFSTAT_ENULL, COMPUTEFSTAT_MSGENULL );
  if (params->returnFaFb)
    {
      ASSERT ( (Fs->Fa != NULL)&&(Fs->Fb != NULL), status, COMPUTEFSTAT_ENULL, COMPUTEFSTAT_MSGENULL );
    }

  /* variable redefinitions for code readability */
  spOrder=params->spinDwnOrder;
  spinDwn=params->spinDwn;
  skyConst=params->skyConst;
  deltaF=(*input)->fft->deltaF;
  nDeltaF=(*input)->fft->data->length;

  /* res=10*(params->mCohSFT); */
  /* This size LUT gives errors ~ 10^-7 with a three-term Taylor series */
  if ( firstCall )
    {
      for (k=0; k <= (LUT_RES/4)*5; k++) {
	sinVal[k] = sin((LAL_TWOPI*k)/(LUT_RES));
	sinVal2PI[k] = sinVal[k]  *  LAL_TWOPI;
	sinVal2PIPI[k] = sinVal2PI[k] * LAL_PI;
      }
      cosVal = sinVal+(LUT_RES/4);
      cosVal2PI = sinVal2PI+(LUT_RES/4);
      cosVal2PIPI = sinVal2PIPI+(LUT_RES/4);

      for (k=0; k <= LUT_RES; k++)
	divLUTtab[k] = (REAL8)k/(REAL8)(LUT_RES);
      firstCall = 0;
    }

  /* this loop computes the values of the phase model */
  xSum=(REAL8 *)LALMalloc(params->SFTno*sizeof(REAL8));
  ySum=(REAL8 *)LALMalloc(params->SFTno*sizeof(REAL8));
  tempInt1=(INT4 *)LALMalloc(params->SFTno*sizeof(INT4));
  for(alpha=0;alpha<params->SFTno;alpha++){
    tempInt1[alpha]=2*alpha*(spOrder+1)+1;
    xSum[alpha]=0.0;
    ySum[alpha]=0.0;
    for(s=0; s<spOrder;s++) {
      xSum[alpha] += spinDwn[s] * skyConst[tempInt1[alpha]+2+2*s];      
      ySum[alpha] += spinDwn[s] * skyConst[tempInt1[alpha]+1+2*s];
    }
  }


  /* Loop over frequencies to be demodulated */
  for(i=0 ; i< params->imax  ; i++ )
  {
    Fa.re =0.0;
    Fa.im =0.0;
    Fb.re =0.0;
    Fb.im =0.0;

    f=params->f0+i*params->df;

    /* Loop over SFTs that contribute to F-stat for a given frequency */
    for(alpha=0;alpha<params->SFTno;alpha++)
      {
        REAL8 tempFreq0, tempFreq1;
        REAL4 tsin, tcos;
        COMPLEX8 *Xalpha=input[alpha]->fft->data->data;
        REAL4 a = params->amcoe->a->data[alpha];
        REAL4 b = params->amcoe->b->data[alpha];
        REAL8 x;
#ifndef USE_LUT_Y
	REAL8 y;
#endif
        REAL4 realP, imagP;             /* real and imaginary parts of P, see CVS */

        /* NOTE: sky-constants are always positive!!
         * this can be seen from there definition (-> documentation)
         * we will use this fact in the following! 
         */
        xTemp= f * skyConst[ tempInt1[ alpha ] ] + xSum[ alpha ];       /* >= 0 !! */
        
        /* this will now be assumed positive, but we double-check this to be sure */
	if  (!finite(xTemp)) {
            fprintf (stderr, "xTemp is not finite\n");
            fprintf (stderr, "DEBUG: loop=%d, xTemp=%f, f=%f, alpha=%d, tempInt1[alpha]=%d\n", 
                     i, xTemp, f, alpha, tempInt1[alpha]);
            fprintf (stderr, "DEBUG: skyConst[ tempInt1[ alpha ] ] = %f, xSum[ alpha ]=%f\n",
                     skyConst[ tempInt1[ alpha ] ], xSum[ alpha ]);
#ifndef USE_BOINC
            fprintf (stderr, "\n*** PLEASE report this bug to pulgroup@gravity.phys.uwm.edu *** \n\n");
#endif
            exit (COMPUTEFSTAT_EXIT_DEMOD);
	}
        if (xTemp < 0) {
            fprintf (stderr, "xTemp >= 0 failed\n");
            fprintf (stderr, "DEBUG: loop=%d, xTemp=%f, f=%f, alpha=%d, tempInt1[alpha]=%d\n", 
                     i, xTemp, f, alpha, tempInt1[alpha]);
            fprintf (stderr, "DEBUG: skyConst[ tempInt1[ alpha ] ] = %f, xSum[ alpha ]=%f\n",
                     skyConst[ tempInt1[ alpha ] ], xSum[ alpha ]);
#ifndef USE_BOINC
            fprintf (stderr, "\n*** PLEASE report this bug to pulgroup@gravity.phys.uwm.edu *** \n\n");
#endif
            exit (COMPUTEFSTAT_EXIT_DEMOD);
	}

        /* find correct index into LUT -- pick closest point */
#ifdef USE_FLOOR
	xTInt =  floor(xTemp);
#else
	xTInt =  (UINT4)xTemp;
#endif
        tempFreq0 = xTemp - xTInt;   /* lies in [0, +1) by definition */

        {
          UINT4 idx  = tempFreq0 * LUT_RES +.5;
          REAL8 d    = tempFreq0 - divLUTtab[idx];
          REAL8 d2   = d*d;
	  
          tsin = sinVal[idx] + d * cosVal2PI[idx] - d2 * sinVal2PIPI[idx];
          tcos = cosVal[idx] - d * sinVal2PI[idx] - d2 * cosVal2PIPI[idx];
	  
          tcos -= 1.0;
        }
	
        {
          REAL8 yTemp = f * skyConst[ tempInt1[ alpha ]-1 ] + ySum[ alpha ];
#ifdef USE_FLOOR
          REAL8 yRem;
          if (yTemp >= 0) {
            yRem = yTemp - floor(yTemp);
          } else {
            /* yRem = yTemp - ceil(yTemp) + 1.0; */
            yRem = yTemp + floor(- yTemp) + 1.0;
          }
#else
	  REAL8 yRem = yTemp - (INT4)(yTemp);
	  if (yRem < 0) { yRem += 1.0f; } /* make sure this is in [0..1) */
#endif
          {
            UINT4 idx  = yRem * LUT_RES + .5;
            REAL8 d    = yRem - divLUTtab[idx];
            REAL8 d2   = d*d;            imagQ = sinVal[idx] + d * cosVal2PI[idx] - d2 * sinVal2PIPI[idx];
            realQ = cosVal[idx] - d * sinVal2PI[idx] - d2 * cosVal2PIPI[idx];
	    
            imagQ = -imagQ;
          }
        }
	
        sftIndex = xTInt - params->Dterms + 1 - params->ifmin;

	if(sftIndex < 0){
              fprintf(stderr,"ERROR! sftIndex = %d < 0 in TestLALDemod run %d\n", sftIndex, cfsRunNo);
              fprintf(stderr," alpha=%d, xTemp=%20.17f, Dterms=%d, ifmin=%d\n",
                      alpha, xTemp, params->Dterms, params->ifmin);
	      ABORT(status, COMPUTEFSTAT_EINPUT, COMPUTEFSTAT_MSGEINPUT);
	}

        tempFreq1 = tempFreq0 + params->Dterms - 1;     /* positive if Dterms > 1 (trivial) */

        x = LAL_TWOPI * tempFreq1;      /* positive! */

        /* we branch now (instead of inside the central loop)
         * depending on wether x can ever become SMALL in the loop or not, 
         * because it requires special treatment in the Dirichlet kernel
         */
        if ( tempFreq0 < LD_SMALL ) 
          {

            realXP=0.0;
            imagXP=0.0;

            /* Loop over terms in Dirichlet Kernel */
            for(k=0; k < klim ; k++)
              {
                COMPLEX8 Xalpha_k = Xalpha[sftIndex];
                sftIndex ++;
                /* If x is small we need correct x->0 limit of Dirichlet kernel */
                if( fabs(x) <  SMALL) 
                  {
                    realXP += Xalpha_k.re;
                    imagXP += Xalpha_k.im;
                  }      
                else
                  {
                    realP = tsin / x;
                    imagP = tcos / x;
                    /* these four lines compute P*xtilde */
                    realXP += Xalpha_k.re * realP;
                    realXP -= Xalpha_k.im * imagP;
                    imagXP += Xalpha_k.re * imagP;
                    imagXP += Xalpha_k.im * realP;
                  }
                
                tempFreq1 --;
                x = LAL_TWOPI * tempFreq1;
                
              } /* for k < klim */

          } /* if x could become close to 0 */
        else
	  /* when optimizing for a specific architecture, we usually don't want to rewrite
	     the whole file, but only the following block of C code, so we insert another
	     hook here, in the hope that we still maintain readability. Also too we'd like
	     to avoid the necessarity to keep changes in other parts of the file in sync
	     between these versions.                                                  BM */
#if defined(USE_X86_GAS)
#include "CFSLALDemodLoop_x86gAss.c"
#elif defined(USE_X86_MAS)
#include "CFSLALDemodLoop_x86MSAss.c"
#elif defined(USE_ALTIVEC)
#include "CFSLALDemodLoop_AltiVec.c"
#elif defined(USE_NDP_VECT)
#include "CFSLALDemodLoop_ndp_vect.c"
#elif defined(USE_NEW_DIV_PART)
#include "CFSLALDemodLoop_div_part.c"
#else
          {
            COMPLEX8 *Xalpha_k = Xalpha + sftIndex;

            realXP=0.0;
            imagXP=0.0;

            /* Loop over terms in Dirichlet Kernel */


            for(k=0; k < klim ; k++)
              {
                REAL4 xinv = (REAL4)OOTWOPI / (REAL4)tempFreq1;
                COMPLEX8 Xa = *Xalpha_k;
                Xalpha_k ++;
                tempFreq1 --;
                
                realP = tsin * xinv;
                imagP = tcos * xinv;
                /* these lines compute P*xtilde */
                realXP += Xa.re * realP - Xa.im * imagP;
                imagXP += Xa.re * imagP + Xa.im * realP;

              } /* for k < klim */

          } /* if x cannot be close to 0 */
#endif

        if(sftIndex-1 > maxSFTindex) {
          fprintf(stderr,"ERROR! sftIndex = %d > %d in TestLALDemod\nalpha=%d,"
                 "xTemp=%20.17f, Dterms=%d, ifmin=%d\n",
                 sftIndex-1, maxSFTindex, alpha, xTemp, params->Dterms, params->ifmin);
	  ABORT(status, COMPUTEFSTAT_EINPUT, COMPUTEFSTAT_MSGEINPUT);
	}


        /* implementation of amplitude demodulation */
        {
          REAL8 realQXP = realXP*realQ-imagXP*imagQ;
          REAL8 imagQXP = realXP*imagQ+imagXP*realQ;
          Fa.re += a*realQXP;
          Fa.im += a*imagQXP;
          Fb.re += b*realQXP;
          Fb.im += b*imagQXP;
        }
      }      

    FaSq = Fa.re*Fa.re+Fa.im*Fa.im;
    FbSq = Fb.re*Fb.re+Fb.im*Fb.im;
    FaFb = Fa.re*Fb.re+Fa.im*Fb.im;
                        
    Fs->F[i] = (4.0/(M*D))*(B*FaSq + A*FbSq - 2.0*C*FaFb);
    if (params->returnFaFb)
      {
        Fs->Fa[i] = Fa;
        Fs->Fb[i] = Fb;
      }


  }
  /* Clean up */
  LALFree(tempInt1);
  LALFree(xSum);
  LALFree(ySum);
  
  RETURN( status );

}

#endif /* USE_R4LALDEMOD, USE_ALTIVEC */
