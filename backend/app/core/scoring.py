class MaturityScoring:
    @staticmethod
    def target_level_from_average(
        average: float,
        basic_threshold: float,
        established_threshold: float,
    ) -> tuple[int, str]:
        if average < basic_threshold:
            return 1, "Basic"
        if average < established_threshold:
            return 2, "Established"
        return 3, "Advanced"

    @staticmethod
    def score_percent_from_level_average(average: float) -> float:
        return max(0.0, min((average / 3.0) * 100.0, 100.0))

    @staticmethod
    def band_from_score_percent(
        score_percent: float,
        basic_threshold: float,
        established_threshold: float,
    ) -> str:
        if score_percent < basic_threshold:
            return "Basic"
        if score_percent < established_threshold:
            return "Established"
        return "Advanced"

    @staticmethod
    def band_from_level(level: int | None, assessment_status: str) -> str:
        if assessment_status != "assessed":
            return "In progress"
        if level == 1:
            return "Basic"
        if level == 2:
            return "Established"
        if level == 3:
            return "Advanced"
        return "Not scored"
