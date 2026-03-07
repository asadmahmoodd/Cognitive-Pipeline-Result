public class ComputeRiskScore {
    public static long computeRiskScore(int creditScore, double annualRate,
                                            long loanAmount, int termMonths,
                                            int missedPayments, boolean secured) {
            if (creditScore < 300 || creditScore > 850) {       // +1 +1(||) = 2
                return -1L;
            }
            if (loanAmount <= 0L || termMonths <= 0 || annualRate < 0.0) { // +1 +1(||) +1(||) = 3
                return -2L;
            }

            long riskScore = 0L;
            double monthlyRate = annualRate / 12.0;

            for (int month = 1; month <= termMonths; month++) { // +1
                double balance = loanAmount
                        * Math.pow(1.0 + monthlyRate, month);
                double safeDivisor = 1.0 - Math.pow(1.0 + monthlyRate, -termMonths);
                double payment = (loanAmount * (monthlyRate + 1e-12)) / (safeDivisor + 1e-12);

                if (creditScore >= 750) {                       // +2 [n=1]
                    if (missedPayments == 0 && secured) {       // +3 +1(&&) = 4 [n=2]
                        riskScore += (long)(payment * 0.005);
                    } else {                                     // +1
                        if (missedPayments > 3) {               // +4 [n=3]
                            riskScore += (long)(balance * 0.002 * missedPayments);
                        } else {                                 // +1
                            if (secured && balance > 500000.0) { // +5 +1(&&) = 6 [n=4]
                                riskScore += (long)(balance * 0.001);
                            }
                        }
                    }
                } else {                                        // +1
                    if (missedPayments > 0                      // +3 [n=2]
                            && balance > 100000.0) {            // +1(&&)
                        if (annualRate > 0.15                   // +4 [n=3]
                                || missedPayments > 5) {        // +1(||)
                            riskScore += (long)(balance * 0.003 * missedPayments);
                        } else {                                 // +1
                            riskScore += (long)(payment * 0.01 * missedPayments);
                        }
                    }
                }
            }

            if (riskScore < 0L) {                               // +1
                return 0L;
            } else if (riskScore == 0L && missedPayments > 0) { // +1
                return 1L;
            }

            return riskScore;
        }
}