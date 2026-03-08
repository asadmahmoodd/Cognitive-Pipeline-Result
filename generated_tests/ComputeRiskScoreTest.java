import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class ComputeRiskScoreTest {

    private final ComputeRiskScore riskCalculator = new ComputeRiskScore();

    @Test
    void testInvalidCreditScoreLow_returnsMinus1() {
        long result = riskCalculator.computeRiskScore(299, 0.10, 1000L, 12, 0, false);
        assertEquals(-1L, result);
    }

    @Test
    void testInvalidCreditScoreHigh_returnsMinus1() {
        long result = riskCalculator.computeRiskScore(900, 0.05, 5000L, 24, 1, true);
        assertEquals(-1L, result);
    }

    @Test
    void testInvalidLoanAmountZero_returnsMinus2() {
        long result = riskCalculator.computeRiskScore(700, 0.05, 0L, 12, 0, false);
        assertEquals(-2L, result);
    }

    @Test
    void testInvalidTermMonthsZero_returnsMinus2() {
        long result = riskCalculator.computeRiskScore(700, 0.00, 1000L, 0, 1, false);
        assertEquals(-2L, result);
    }

    @Test
    void testInvalidAnnualRateNegative_returnsMinus2() {
        long result = riskCalculator.computeRiskScore(700, -0.01, 1000L, 12, 0, false);
        assertEquals(-2L, result);
    }

    @Test
    void testHighCredit_noMissed_secured_oneMonth() {
        long result = riskCalculator.computeRiskScore(800, 0.00, 100000L, 1, 0, true);
        assertEquals(500L, result);
    }

    @Test
    void testHighCredit_missedPaymentsGreaterThan3_multipleMonths() {
        long result = riskCalculator.computeRiskScore(780, 0.00, 200000L, 2, 4, false);
        assertEquals(3200L, result);
    }

    @Test
    void testHighCredit_missedPaymentsBetween1And3_securedAndLargeBalance() {
        long result = riskCalculator.computeRiskScore(760, 0.00, 600000L, 3, 2, true);
        assertEquals(1800L, result);
    }

    @Test
    void testHighCredit_missedPaymentsPositive_notSecured_smallBalance_returns1() {
        long result = riskCalculator.computeRiskScore(790, 0.00, 400000L, 2, 1, false);
        assertEquals(1L, result);
    }

    @Test
    void testLowCredit_conditionTrue_leftSideOfOr_annualRateHigh() {
        long result = riskCalculator.computeRiskScore(700, 0.24, 123456L, 1, 1, false);
        assertEquals(377L, result);
    }

    @Test
    void testLowCredit_conditionTrue_rightSideOfOr_missedPaymentsHigh() {
        long result = riskCalculator.computeRiskScore(700, 0.00, 200000L, 1, 6, false);
        assertEquals(3600L, result);
    }

    @Test
    void testLowCredit_conditionTrue_elseBranch_usesPaymentTimesMissed_multipleMonths() {
        long result = riskCalculator.computeRiskScore(700, 0.00, 150001L, 2, 2, false);
        assertEquals(6000L, result);
    }

    @Test
    void testLowCredit_conditionFalse_dueToZeroMissedPayments_returns0() {
        long result = riskCalculator.computeRiskScore(650, 0.00, 50000L, 3, 0, false);
        assertEquals(0L, result);
    }

    @Test
    void testLowCredit_conditionFalse_dueToSmallBalance_returns1() {
        long result = riskCalculator.computeRiskScore(700, 0.00, 95000L, 2, 2, false);
        assertEquals(1L, result);
    }
}