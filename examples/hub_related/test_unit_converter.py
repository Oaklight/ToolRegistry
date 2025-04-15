import unittest
from toolregistry.hub.unit_converter import UnitConverter


class TestUnitConverter(unittest.TestCase):
    def test_temperature_conversions(self):
        self.assertAlmostEqual(UnitConverter.celsius_to_fahrenheit(0), 32)
        self.assertAlmostEqual(UnitConverter.fahrenheit_to_celsius(32), 0)
        self.assertAlmostEqual(UnitConverter.kelvin_to_celsius(273.15), 0, places=2)
        self.assertAlmostEqual(UnitConverter.celsius_to_kelvin(0), 273.15, places=2)

    def test_length_conversions(self):
        self.assertAlmostEqual(UnitConverter.meters_to_feet(1), 3.28084, places=5)
        self.assertAlmostEqual(UnitConverter.feet_to_meters(3.28084), 1, places=5)
        self.assertAlmostEqual(UnitConverter.centimeters_to_inches(2.54), 1, places=5)
        self.assertAlmostEqual(UnitConverter.inches_to_centimeters(1), 2.54, places=5)

    def test_weight_conversions(self):
        self.assertAlmostEqual(UnitConverter.kilograms_to_pounds(1), 2.20462, places=5)
        self.assertAlmostEqual(UnitConverter.pounds_to_kilograms(2.20462), 1, places=5)

    def test_time_conversions(self):
        self.assertAlmostEqual(UnitConverter.seconds_to_minutes(60), 1)
        self.assertAlmostEqual(UnitConverter.minutes_to_seconds(1), 60)

    def test_capacity_conversions(self):
        self.assertAlmostEqual(UnitConverter.liters_to_gallons(3.78541), 1, places=5)
        self.assertAlmostEqual(UnitConverter.gallons_to_liters(1), 3.78541, places=5)

    def test_area_conversions(self):
        self.assertAlmostEqual(
            UnitConverter.square_meters_to_square_feet(1), 10.7639, places=4
        )
        self.assertAlmostEqual(
            UnitConverter.square_feet_to_square_meters(10.7639), 1, places=4
        )

    def test_speed_conversions(self):
        self.assertAlmostEqual(UnitConverter.kmh_to_mph(1.60934), 1, places=5)
        self.assertAlmostEqual(UnitConverter.mph_to_kmh(1), 1.60934, places=5)

    def test_data_storage_conversions(self):
        self.assertAlmostEqual(UnitConverter.bits_to_bytes(8), 1)
        self.assertAlmostEqual(UnitConverter.bytes_to_kilobytes(1024), 1)
        self.assertAlmostEqual(UnitConverter.kilobytes_to_megabytes(1024), 1)

    def test_pressure_conversions(self):
        self.assertAlmostEqual(UnitConverter.pascal_to_bar(100000), 1)
        self.assertAlmostEqual(UnitConverter.bar_to_atm(1.01325), 1, places=4)

    def test_power_conversions(self):
        self.assertAlmostEqual(UnitConverter.watts_to_kilowatts(1000), 1)
        self.assertAlmostEqual(
            UnitConverter.kilowatts_to_horsepower(1), 1.34102, places=5
        )

    def test_energy_conversions(self):
        self.assertAlmostEqual(UnitConverter.joules_to_calories(4.184), 1)
        self.assertAlmostEqual(
            UnitConverter.calories_to_kilowatt_hours(860420), 1, places=3
        )

    def test_frequency_conversions(self):
        self.assertAlmostEqual(UnitConverter.hertz_to_kilohertz(1000), 1)
        self.assertAlmostEqual(UnitConverter.kilohertz_to_megahertz(1000), 1)

    def test_fuel_economy_conversions(self):
        self.assertAlmostEqual(UnitConverter.km_per_liter_to_mpg(1), 2.35215, places=5)
        self.assertAlmostEqual(UnitConverter.mpg_to_km_per_liter(2.35215), 1, places=5)

    def test_electrical_conversions(self):
        self.assertAlmostEqual(UnitConverter.ampere_to_milliampere(1), 1000)
        self.assertAlmostEqual(UnitConverter.volt_to_kilovolt(1000), 1)
        self.assertAlmostEqual(UnitConverter.ohm_to_kiloohm(1000), 1)

    def test_magnetic_conversions(self):
        self.assertAlmostEqual(UnitConverter.weber_to_tesla(1, 2), 0.5)
        self.assertAlmostEqual(UnitConverter.gauss_to_tesla(10000), 1)
        self.assertAlmostEqual(UnitConverter.tesla_to_weber(1, 2), 2)
        self.assertAlmostEqual(UnitConverter.tesla_to_gauss(1), 10000)

    def test_radiation_conversions(self):
        self.assertAlmostEqual(UnitConverter.gray_to_sievert(1), 1)

    def test_light_intensity_conversions(self):
        self.assertAlmostEqual(UnitConverter.lux_to_lumen(10, 2), 20)
        self.assertAlmostEqual(UnitConverter.lumen_to_lux(20, 2), 10)


if __name__ == "__main__":
    unittest.main()
